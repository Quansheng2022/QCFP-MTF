# coding: utf-8
"""UNKNOWN Resolution Pipeline（P0-6）

状态：OPTIONAL_EXECUTION_EXTENSION（P1-7 目标重新对齐）
只服务于可选的 Broker/Paper 执行扩展；决策支持资格不依赖本模块。

把 Broker UNKNOWN 从普通状态提升为严格 Risk State：

    UNKNOWN_DETECTED
        ↓
    ORDER_QUERY → FILL_QUERY → POSITION_QUERY → RECONCILE
        ↓
    RESOLVED_FILLED / RESOLVED_REJECTED /
    RESOLVED_CANCELLED / RESOLVED_NO_ORDER
        ↓
    RISK_UNBLOCKED

仍无法确定：
    UNRESOLVED_UNKNOWN → NO_NEW_RISK

Hard Gate（永久）：
    blind_resend_count == 0
    同一个 (decision_id, order_intent_id) 存在 unresolved UNKNOWN 时，
    禁止生成第二张等价 order（assert_no_blind_resend → BLOCKED）。
"""

import json
from datetime import datetime


UNKNOWN_FSM_PIPELINE = ("UNKNOWN_DETECTED", "ORDER_QUERY", "FILL_QUERY",
                        "POSITION_QUERY", "RECONCILE")
RESOLVED_TERMINALS = ("RESOLVED_FILLED", "RESOLVED_REJECTED",
                      "RESOLVED_CANCELLED", "RESOLVED_NO_ORDER")


def _payload_of(ev) -> dict:
    p = ev.get("payload")
    if isinstance(p, dict):
        return p
    if isinstance(p, str):
        try:
            return json.loads(p)
        except Exception:
            return {}
    return {}


def _latency_ms(start, end):
    try:
        a = datetime.fromisoformat(str(start).replace(" ", "T"))
        b = datetime.fromisoformat(str(end).replace(" ", "T"))
        return max(0, int((b - a).total_seconds() * 1000))
    except Exception:
        return None


def unknown_resolution_pipeline(events) -> dict:
    """单个 (decision_id, order_intent_id) 的 UNKNOWN 事件序列 → FSM 终态。

    events：按 event_seq 升序的 dict 列表
        （event_type / event_time / payload.resolution_status）
    """
    events = list(events or [])
    unknown_seen = False
    unknown_at = ""
    query_attempts = 0
    resolution = None
    resolution_at = ""
    for ev in events:
        et = str(ev.get("event_type") or "").upper()
        if et == "ORDER_UNKNOWN":
            unknown_seen = True
            unknown_at = ev.get("event_time") or ""
        elif et == "UNKNOWN_QUERY":
            if unknown_seen:
                query_attempts += 1
        elif et == "UNKNOWN_RESOLVED":
            resolution = _payload_of(ev).get("resolution_status")
            resolution_at = ev.get("event_time") or ""
    if not unknown_seen:
        return {"status": "NO_UNKNOWN", "resolved": False,
                "risk_unblocked": False, "no_new_risk": False,
                "query_attempt_count": 0,
                "resolution_latency_ms": None}
    if resolution in RESOLVED_TERMINALS:
        return {"status": resolution, "resolved": True,
                "risk_unblocked": True, "no_new_risk": False,
                "query_attempt_count": query_attempts,
                "resolution_latency_ms": _latency_ms(
                    unknown_at, resolution_at)}
    return {"status": "UNRESOLVED_UNKNOWN", "resolved": False,
            "risk_unblocked": False, "no_new_risk": True,
            "query_attempt_count": query_attempts,
            "resolution_latency_ms": None}


def unresolved_unknown_exists(conn, decision_id, order_intent_id) -> bool:
    """同 (decision_id, order_intent_id) 是否存在 unresolved UNKNOWN。

    ORDER_UNKNOWN 存在且其后没有 UNKNOWN_RESOLVED → True
    （禁止生成第二张等价 order）。"""
    try:
        rows = conn.execute(
            "SELECT event_type FROM qcfp_runtime_event_ledger "
            "WHERE decision_id=? AND order_intent_id=? "
            "ORDER BY event_seq",
            (decision_id, order_intent_id)).fetchall()
    except Exception:
        return False
    seen_unknown = False
    for r in rows:
        et = str(r["event_type"] or "").upper()
        if et == "ORDER_UNKNOWN":
            seen_unknown = True
        elif et == "UNKNOWN_RESOLVED" and seen_unknown:
            return False
    return seen_unknown


def assert_no_blind_resend(conn, decision_id, order_intent_id,
                           new_order_id="") -> dict:
    """Hard Gate：unresolved UNKNOWN 存在 → 禁止新等价 order。"""
    if unresolved_unknown_exists(conn, decision_id, order_intent_id):
        return {"blocked": True,
                "reason": "UNRESOLVED_UNKNOWN_EXISTS",
                "decision_id": decision_id,
                "order_intent_id": order_intent_id,
                "new_order_id": new_order_id,
                "rule": "unresolved UNKNOWN → 禁止第二张等价 order"}
    return {"blocked": False, "decision_id": decision_id,
            "order_intent_id": order_intent_id,
            "new_order_id": new_order_id}


def unknown_resolution_metrics_from_events(conn, release_id,
                                           start, end) -> dict:
    """从 Runtime Event Ledger 聚合 UNKNOWN Resolution 指标：
        unknown_count / resolved_unknown / unresolved_unknown /
        query_attempt_count / blind_resend_count /
        resolution_latency_ms / max_resolution_latency
    blind_resend_count：ORDER_UNKNOWN 未 resolved 时又发 ORDER_SENT。"""
    try:
        cols = [r[1] for r in conn.execute(
            "PRAGMA table_info(qcfp_runtime_event_ledger)").fetchall()]
    except Exception:
        cols = []
    if "order_intent_id" not in cols or "event_time" not in cols:
        return {
            "unknown_count": 0, "resolved_unknown": 0,
            "unresolved_unknown": 0, "query_attempt_count": 0,
            "blind_resend_count": 0, "resolution_latency_ms": None,
            "max_resolution_latency": None,
            "rule": "blind_resend_count 永久 Hard Gate = 0；"
                    "UNRESOLVED_UNKNOWN → NO_NEW_RISK"}
    rows = conn.execute(
        "SELECT event_seq, event_type, decision_id, order_intent_id, "
        "event_time, payload FROM qcfp_runtime_event_ledger "
        "WHERE release_id=? AND event_type IN "
        "('ORDER_UNKNOWN','UNKNOWN_QUERY','UNKNOWN_RESOLVED',"
        "'ORDER_SENT') "
        "AND substr(event_time,1,10)>=? AND substr(event_time,1,10)<=? "
        "ORDER BY event_seq",
        (release_id, start, end)).fetchall()
    groups = {}
    order = []
    for r in rows:
        key = (r["decision_id"] or "", r["order_intent_id"] or "")
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(dict(r))
    unknown_count = 0
    resolved_unknown = 0
    unresolved_unknown = 0
    query_attempt_count = 0
    blind_resend_count = 0
    latencies = []
    for key in order:
        events = groups[key]
        has_unknown = any(
            str(e.get("event_type") or "").upper() == "ORDER_UNKNOWN"
            for e in events)
        if not has_unknown:
            continue
        unknown_count += 1
        pipe = unknown_resolution_pipeline(events)
        query_attempt_count += int(pipe.get("query_attempt_count") or 0)
        if pipe["resolved"]:
            resolved_unknown += 1
            lat = pipe.get("resolution_latency_ms")
            if lat is not None:
                latencies.append(lat)
        else:
            unresolved_unknown += 1
        # blind resend：UNKNOWN 之后、RESOLVED 之前又发 ORDER_SENT
        open_unknown = False
        for e in events:
            et = str(e.get("event_type") or "").upper()
            if et == "ORDER_UNKNOWN":
                open_unknown = True
            elif et == "UNKNOWN_RESOLVED":
                open_unknown = False
            elif et == "ORDER_SENT" and open_unknown:
                blind_resend_count += 1
    return {
        "unknown_count": unknown_count,
        "resolved_unknown": resolved_unknown,
        "unresolved_unknown": unresolved_unknown,
        "query_attempt_count": query_attempt_count,
        "blind_resend_count": blind_resend_count,
        "resolution_latency_ms": round(
            sum(latencies) / len(latencies)) if latencies else None,
        "max_resolution_latency": max(latencies) if latencies else None,
        "rule": "blind_resend_count 永久 Hard Gate = 0；"
                "UNRESOLVED_UNKNOWN → NO_NEW_RISK",
    }
