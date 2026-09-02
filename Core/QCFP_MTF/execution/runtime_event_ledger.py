# coding: utf-8
"""Runtime Event Ledger（Runtime Evidence Wiring：第 2/8/9 项）

唯一真实运行事件事实源（qcfp_runtime_event_ledger）：
    ORDER_INTENT / ORDER_SENT / ORDER_ACK / PARTIAL_FILL / FILL /
    ORDER_REJECT / ORDER_CANCEL / ORDER_UNKNOWN / BROKER_POSITION /
    RECONCILIATION / INCIDENT / RECOVERY / REPLAY / REACTIVATION

Runtime Evidence Wiring 修改：
    * event_seq INTEGER AUTOINCREMENT 作为链顺序（不再用 MAX(event_id)）；
    * current_event_hash 覆盖全部不可变事实字段（费用/内外仓位等）；
    * verify 重新计算 payload_hash 与 current_event_hash +
      sequence continuity（不是只看链指针）；
    * 写入前强制 validate_runtime_identity（event → decision → release →
      certificate 100% 可反查；identity mismatch → EVENT_APPEND_REJECTED）；
    * 表结构由 sql/create_qcfp_tables.sql 拥有；本模块只提供显式
      ensure_runtime_event_table()（测试/本地），不偷偷自动建表。
"""

import hashlib
import json


RUNTIME_EVENT_TYPES = (
    "ORDER_INTENT", "ORDER_SENT", "ORDER_ACK", "PARTIAL_FILL", "FILL",
    "ORDER_REJECT", "ORDER_CANCEL", "ORDER_UNKNOWN",
    "UNKNOWN_QUERY", "UNKNOWN_RESOLVED",
    "BROKER_POSITION", "RECONCILIATION",
    "INCIDENT", "RECOVERY", "REPLAY", "REACTIVATION",
)

SYSTEM_EVENT_TYPES = ("INCIDENT", "RECOVERY", "REPLAY", "REACTIVATION")

EXECUTION_MODES = ("SHADOW", "PAPER", "SMALL_LIVE")

RUNTIME_EVENT_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS qcfp_runtime_event_ledger (
    event_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT UNIQUE,
    event_type TEXT, event_time TEXT,
    decision_id TEXT, release_id TEXT, certificate_id TEXT,
    execution_mode TEXT, account_id TEXT, stock_code TEXT,
    order_intent_id TEXT, broker_order_id TEXT,
    side TEXT, requested_qty REAL, filled_qty REAL, fill_price REAL,
    commission REAL, stamp_duty REAL, exchange_fee REAL, other_fee REAL,
    internal_position REAL, broker_position REAL,
    reconciliation_status TEXT, incident_id TEXT,
    payload TEXT, payload_hash TEXT,
    previous_event_hash TEXT, current_event_hash TEXT
)
"""

# 全部不可变事实字段（Hash 必须覆盖费用/内外仓位等关键字段）
RUNTIME_EVENT_HASH_FIELDS = (
    "event_id", "event_type", "event_time", "decision_id",
    "release_id", "certificate_id", "execution_mode", "account_id",
    "stock_code", "order_intent_id", "broker_order_id", "side",
    "requested_qty", "filled_qty", "fill_price",
    "commission", "stamp_duty", "exchange_fee", "other_fee",
    "internal_position", "broker_position",
    "reconciliation_status", "incident_id",
)

NUMERIC_HASH_FIELDS = (
    "requested_qty", "filled_qty", "fill_price",
    "commission", "stamp_duty", "exchange_fee", "other_fee",
    "internal_position", "broker_position",
)


def ensure_runtime_event_table(conn) -> None:
    """显式建表（测试/本地用）。Production schema 由
    sql/create_qcfp_tables.sql 迁移拥有。"""
    conn.execute(RUNTIME_EVENT_TABLE_DDL)


def _payload_hash(payload) -> str:
    raw = payload if isinstance(payload, str) else \
        json.dumps(payload or {}, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def runtime_event_hash(prev_hash, event: dict) -> str:
    """覆盖全部不可变事实字段 + payload_hash + prev。"""
    payload = {}
    for k in RUNTIME_EVENT_HASH_FIELDS:
        v = event.get(k)
        # SQLite REAL 返回 float；append 时可能为 int → 统一数值规范
        if k in NUMERIC_HASH_FIELDS and v is not None:
            try:
                v = float(v)
            except (TypeError, ValueError):
                v = None
        payload[k] = v
    payload["payload_hash"] = event.get("payload_hash") or \
        _payload_hash(event.get("payload"))
    payload["prev"] = prev_hash or ""
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                     default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def validate_runtime_identity(conn, event: dict,
                              require_decision=True) -> dict:
    """写入前强制 identity cross-binding（第 2 项）：

        event.decision_id
            ↓ qcfp_decision_ledger（ACTIVE）
            ↓ context.release_identity.release_id == event.release_id

    SMALL_LIVE 额外要求 certificate_id 存在且
    certificate.decision_id == event.decision_id 且
    certificate.release_id  == event.release_id。

    系统事件（INCIDENT/RECOVERY/REPLAY/REACTIVATION）可无 decision_id，
    但 release_id 必须存在。"""
    import json as _json
    decision_id = event.get("decision_id") or ""
    release_id = event.get("release_id") or ""
    mode = str(event.get("execution_mode") or "").upper()
    event_type = str(event.get("event_type") or "").upper()
    reasons = []
    if not release_id:
        reasons.append("RELEASE_ID_REQUIRED")
    if mode and mode not in EXECUTION_MODES:
        reasons.append("INVALID_EXECUTION_MODE")
    is_system = event_type in SYSTEM_EVENT_TYPES
    if require_decision and not is_system and not decision_id:
        reasons.append("DECISION_ID_REQUIRED")
    if reasons:
        return {"valid": False, "reasons": reasons, "mode": mode}
    if not is_system and decision_id:
        row = conn.execute(
            "SELECT context FROM qcfp_decision_ledger "
            "WHERE decision_id=? AND status='ACTIVE' "
            "ORDER BY id DESC LIMIT 1", (decision_id,)).fetchone()
        if row is None:
            return {"valid": False,
                    "reasons": ["DECISION_NOT_IN_LEDGER"], "mode": mode}
        ctx = {}
        try:
            ctx = _json.loads(row["context"] or "{}")
        except Exception:
            ctx = {}
        decision_release = (ctx.get("release_identity") or {}).get(
            "release_id") or ""
        if decision_release and str(decision_release) != str(release_id):
            return {"valid": False,
                    "reasons": ["RELEASE_ID_MISMATCH_WITH_DECISION"],
                    "mode": mode, "decision_release": decision_release,
                    "event_release": release_id}
    if mode == "SMALL_LIVE" and not is_system:
        certificate_id = event.get("certificate_id") or ""
        if not certificate_id:
            reasons.append("CERTIFICATE_ID_REQUIRED")
        else:
            cert = conn.execute(
                "SELECT decision_id, release_id FROM "
                "qcfp_decision_certificate WHERE certificate_id=? LIMIT 1",
                (certificate_id,)).fetchone()
            if cert is None:
                reasons.append("CERTIFICATE_NOT_FOUND")
            else:
                if str(cert["decision_id"]) != str(decision_id):
                    reasons.append("CERTIFICATE_DECISION_MISMATCH")
                if str(cert["release_id"] or "") != str(release_id):
                    reasons.append("CERTIFICATE_RELEASE_MISMATCH")
        if reasons:
            return {"valid": False, "reasons": reasons, "mode": mode}
    return {"valid": True, "reasons": [], "mode": mode}


def append_runtime_event(conn, event: dict,
                         require_decision=True) -> dict:
    """先 Validate Identity → 再 Append（禁止 Append 后检查）。

    Identity mismatch → EVENT_APPEND_REJECTED（不写库）。"""
    identity = validate_runtime_identity(conn, event,
                                         require_decision=require_decision)
    if not identity["valid"]:
        return {"event_id": event.get("event_id"),
                "inserted": 0, "rejected": True,
                "reason": "EVENT_APPEND_REJECTED",
                "identity": identity}
    prev = _last_event_hash(conn)
    payload = event.get("payload") or {}
    event["payload"] = json.dumps(payload, ensure_ascii=False,
                                  default=str)
    event["payload_hash"] = _payload_hash(event["payload"])
    current = runtime_event_hash(prev, event)
    event["previous_event_hash"] = prev
    event["current_event_hash"] = current
    cols = list(RUNTIME_EVENT_HASH_FIELDS) + list(
        ("payload", "payload_hash", "previous_event_hash",
         "current_event_hash"))
    cur = conn.execute(
        f"INSERT OR IGNORE INTO qcfp_runtime_event_ledger "
        f"({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
        [event.get(c) for c in cols])
    conn.commit()
    return {"event_id": event.get("event_id"),
            "previous_event_hash": prev,
            "current_event_hash": current,
            "inserted": cur.rowcount,
            "rejected": False}


def _last_event_hash(conn) -> str:
    try:
        r = conn.execute(
            "SELECT current_event_hash FROM qcfp_runtime_event_ledger "
            "ORDER BY event_seq DESC LIMIT 1").fetchone()
        return r[0] if r and r[0] else ""
    except Exception:
        return ""


def verify_runtime_event_chain(conn) -> dict:
    """四重验证（第 8A 项）：
        1) 重新计算 payload_hash
        2) 重新计算 current_event_hash
        3) previous_hash 连续性
        4) event_seq 连续性
    """
    rows = conn.execute(
        "SELECT event_seq, event_id, event_type, event_time, decision_id, "
        "release_id, certificate_id, execution_mode, account_id, "
        "stock_code, order_intent_id, broker_order_id, side, "
        "requested_qty, filled_qty, fill_price, commission, stamp_duty, "
        "exchange_fee, other_fee, internal_position, broker_position, "
        "reconciliation_status, incident_id, payload, payload_hash, "
        "previous_event_hash, current_event_hash "
        "FROM qcfp_runtime_event_ledger ORDER BY event_seq").fetchall()
    prev = ""
    mismatches = []
    for i, r in enumerate(rows, start=1):
        event = {k: r[k] for k in RUNTIME_EVENT_HASH_FIELDS}
        event["payload"] = r["payload"]
        event["payload_hash"] = r["payload_hash"]
        # 1) payload_hash 重算
        if _payload_hash(r["payload"] or "") != (r["payload_hash"] or ""):
            mismatches.append({"event_id": r["event_id"],
                               "type": "PAYLOAD_HASH_MISMATCH"})
        # 2) current_event_hash 重算
        expected_current = runtime_event_hash(r["previous_event_hash"],
                                              event)
        if expected_current != (r["current_event_hash"] or ""):
            mismatches.append({"event_id": r["event_id"],
                               "type": "CURRENT_HASH_MISMATCH"})
        # 3) prev 连续性
        if (r["previous_event_hash"] or "") != prev:
            mismatches.append({"event_id": r["event_id"],
                               "type": "PREV_HASH_BREAK",
                               "expected_prev": prev,
                               "stored_prev": r["previous_event_hash"]})
        prev = r["current_event_hash"] or prev
        # 4) sequence 连续性
        if r["event_seq"] != i:
            mismatches.append({"event_id": r["event_id"],
                               "type": "SEQUENCE_GAP",
                               "expected_seq": i,
                               "actual_seq": r["event_seq"]})
    return {"checked": len(rows), "mismatches": mismatches,
            "verified": not mismatches,
            "chain_tail": prev}


# ---------------------------------------------------------------------------
# 第 9 项：Incident → Recovery → Replay → Reactivation 真实 Event Chain
# ---------------------------------------------------------------------------

def trusted_checkpoint(conn, incident_id, release_id, decision_id="",
                       decision_path_hash="", internal_position=None,
                       broker_position=None, config_hash="") -> dict:
    """Incident 时冻结最后可信状态（last_trusted_event_*）。"""
    last = conn.execute(
        "SELECT event_seq, current_event_hash, event_id "
        "FROM qcfp_runtime_event_ledger ORDER BY event_seq DESC LIMIT 1"
    ).fetchone()
    return {
        "incident_id": incident_id,
        "release_id": release_id,
        "last_trusted_event_seq": last["event_seq"] if last else 0,
        "last_trusted_event_hash": last["current_event_hash"] if last
        else "",
        "last_trusted_event_id": last["event_id"] if last else "",
        "last_trusted_decision_id": decision_id,
        "last_decision_path_hash": decision_path_hash,
        "last_internal_position": internal_position,
        "last_broker_position": broker_position,
        "config_hash": config_hash,
    }


def append_incident_event(conn, incident_id, release_id,
                          failure_kind="SYSTEM_FAILURE",
                          checkpoint=None, decision_id="",
                          event_time="") -> dict:
    """INCIDENT 事件（系统事件，不需要 decision cross-bind）。"""
    from datetime import datetime
    event_time = event_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return append_runtime_event(
        conn, {
            "event_id": f"INC-{incident_id}",
            "event_type": "INCIDENT",
            "event_time": event_time,
            "decision_id": decision_id,
            "release_id": release_id,
            "execution_mode": "SMALL_LIVE",
            "incident_id": incident_id,
            "payload": {"failure_kind": failure_kind,
                        "checkpoint": checkpoint or {}},
        }, require_decision=False)


def append_recovery_event(conn, incident_id, release_id, root_cause="",
                          fix="", replay_hash="", event_time="") -> dict:
    from datetime import datetime
    event_time = event_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return append_runtime_event(
        conn, {
            "event_id": f"REC-{incident_id}",
            "event_type": "RECOVERY",
            "event_time": event_time,
            "decision_id": "",
            "release_id": release_id,
            "execution_mode": "SMALL_LIVE",
            "incident_id": incident_id,
            "payload": {"root_cause": root_cause, "fix": fix,
                        "replay_hash": replay_hash},
        }, require_decision=False)


def append_replay_event(conn, incident_id, release_id, replay_hash="",
                        verified=False, event_time="") -> dict:
    from datetime import datetime
    event_time = event_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return append_runtime_event(
        conn, {
            "event_id": f"RP-{incident_id}",
            "event_type": "REPLAY",
            "event_time": event_time,
            "decision_id": "",
            "release_id": release_id,
            "execution_mode": "SMALL_LIVE",
            "incident_id": incident_id,
            "payload": {"replay_hash": replay_hash, "verified": verified},
        }, require_decision=False)


def append_reactivation_event(conn, incident_id, release_id,
                              certificate_id, replay_hash="",
                              approval_identity="", event_time="") -> dict:
    """REACTIVATION 事件（绑定 ReactivationCertificate）。"""
    from datetime import datetime
    event_time = event_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return append_runtime_event(
        conn, {
            "event_id": f"RA-{incident_id}",
            "event_type": "REACTIVATION",
            "event_time": event_time,
            "decision_id": "",
            "release_id": release_id,
            "execution_mode": "SMALL_LIVE",
            "incident_id": incident_id,
            "certificate_id": certificate_id,
            "payload": {"replay_hash": replay_hash,
                        "approval_identity": approval_identity},
        }, require_decision=False)
