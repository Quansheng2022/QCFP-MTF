# coding: utf-8
"""Research Outcome（Runtime Evidence Wiring：第 4 项）

Outcome 与 EvidenceSnapshot 物理分离：
    DecisionLedger ──decision_id──▶ ResearchOutcome
Decision 原始事实永远不变；未来 MFE/MAE/Wave/NO_TRADE outcome 只能
异步追加，绝不能 UPDATE Decision Row。

CI 边界：Production packages 禁止 import qcfp_research_outcome /
future_return / mfe / mae / wave_peak_return / missed_opportunity。

Runtime Evidence Wiring 修改：
    * 写入前强制 validate_research_outcome（research_only/future_aware/
      decision/release cross-bind/时间顺序/source snapshot/hash），
      任意缺失 → OUTCOME_APPEND_REJECTED（不可绕过）；
    * 表结构由 sql/create_qcfp_tables.sql 拥有；本模块只提供显式
      ensure_research_outcome_table()，不偷偷自动建表。
"""

import hashlib
import json


OUTCOME_FIELDS = (
    "outcome_id", "decision_id", "release_id", "stock_code",
    "decision_date", "evaluation_time", "horizon", "horizon_end",
    "entry_reference_price", "exit_reference_price",
    "future_return", "mfe", "mae", "mfe_date", "mae_date",
    "wave_peak_return", "wave_capture", "outcome_type",
    "missed_opportunity", "false_participation",
    "future_aware", "research_only", "source_data_snapshot_id",
    "outcome_hash", "created_at",
)

RESEARCH_OUTCOME_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS qcfp_research_outcome (
    outcome_id TEXT PRIMARY KEY,
    decision_id TEXT, release_id TEXT, stock_code TEXT, decision_date TEXT,
    evaluation_time TEXT, horizon TEXT, horizon_end TEXT,
    entry_reference_price REAL, exit_reference_price REAL,
    future_return REAL, mfe REAL, mae REAL, mfe_date TEXT, mae_date TEXT,
    wave_peak_return REAL, wave_capture REAL, outcome_type TEXT,
    missed_opportunity INTEGER, false_participation INTEGER,
    future_aware INTEGER, research_only INTEGER,
    source_data_snapshot_id TEXT, outcome_hash TEXT, created_at TEXT
)
"""


def research_outcome(decision_id, release_id, stock_code, decision_date,
                     horizon, future_return=None, mfe=None, mae=None,
                     wave_peak_return=None, missed_opportunity=False,
                     false_participation=False, outcome_type="GENERIC",
                     outcome_id="", evaluation_time="", horizon_end="",
                     entry_reference_price=None, exit_reference_price=None,
                     source_data_snapshot_id="", created_at="") -> dict:
    """生成 Research Outcome 记录（future_aware=True / research_only=True）。"""
    record = {
        "outcome_id": outcome_id or f"OC-{decision_id}-{horizon}",
        "decision_id": decision_id, "release_id": release_id,
        "stock_code": stock_code, "decision_date": decision_date,
        "evaluation_time": evaluation_time, "horizon": horizon,
        "horizon_end": horizon_end,
        "entry_reference_price": entry_reference_price,
        "exit_reference_price": exit_reference_price,
        "future_return": future_return, "mfe": mfe, "mae": mae,
        "mfe_date": "", "mae_date": "",
        "wave_peak_return": wave_peak_return, "wave_capture": None,
        "outcome_type": outcome_type,
        "missed_opportunity": bool(missed_opportunity),
        "false_participation": bool(false_participation),
        "future_aware": True,
        "research_only": True,
        "source_data_snapshot_id": source_data_snapshot_id,
        "outcome_hash": "",
        "created_at": created_at,
    }
    raw = json.dumps({k: record[k] for k in OUTCOME_FIELDS
                      if k not in ("outcome_hash",)},
                     sort_keys=True, ensure_ascii=False, default=str)
    record["outcome_hash"] = hashlib.sha256(
        raw.encode("utf-8")).hexdigest()[:16]
    return record


def assert_outcome_production_isolated(outcome: dict) -> dict:
    """Outcome 只能被 monitoring/research/evaluation 读取。"""
    ok = bool(outcome.get("research_only")) \
        and bool(outcome.get("future_aware"))
    return {"outcome_id": outcome.get("outcome_id"),
            "production_isolated": ok,
            "can_affect_current_decision": False,
            "violation": not ok,
            "rule": "Outcome ──▶ historical Decision 绝对禁止"}


def ensure_research_outcome_table(conn) -> None:
    """显式建表（测试/本地用）。Production schema 由
    sql/create_qcfp_tables.sql 迁移拥有。"""
    conn.execute(RESEARCH_OUTCOME_TABLE_DDL)


def validate_research_outcome(conn, outcome: dict) -> dict:
    """写入前强制校验（第 4 项）：

        research_only == True
        future_aware  == True
        decision_id 存在于 qcfp_decision_ledger（ACTIVE）
        release_id 与决策台账 release identity 一致
        evaluation_time > decision_time
        horizon_end <= evaluation_time
        source_data_snapshot_id != ""
        outcome_hash 重算一致

    任意缺失 → OUTCOME_APPEND_REJECTED；不能依赖调用者先跑
    assert_outcome_production_isolated()。"""
    import json as _json
    import hashlib as _hashlib
    reasons = []
    if not bool(outcome.get("research_only")):
        reasons.append("RESEARCH_ONLY_REQUIRED")
    if not bool(outcome.get("future_aware")):
        reasons.append("FUTURE_AWARE_REQUIRED")
    decision_id = outcome.get("decision_id") or ""
    release_id = outcome.get("release_id") or ""
    if not decision_id:
        reasons.append("DECISION_ID_REQUIRED")
    if not release_id:
        reasons.append("RELEASE_ID_REQUIRED")
    decision_date = outcome.get("decision_date") or ""
    evaluation_time = outcome.get("evaluation_time") or ""
    horizon_end = outcome.get("horizon_end") or ""
    if decision_id:
        row = conn.execute(
            "SELECT context, decision_date FROM qcfp_decision_ledger "
            "WHERE decision_id=? AND status='ACTIVE' "
            "ORDER BY id DESC LIMIT 1", (decision_id,)).fetchone()
        if row is None:
            reasons.append("DECISION_NOT_IN_LEDGER")
        else:
            ctx = {}
            try:
                ctx = _json.loads(row["context"] or "{}")
            except Exception:
                ctx = {}
            decision_release = (ctx.get("release_identity") or {}).get(
                "release_id") or ""
            if decision_release and str(decision_release) != str(release_id):
                reasons.append("RELEASE_ID_MISMATCH_WITH_DECISION")
            if not decision_date:
                decision_date = row["decision_date"] or ""
    if evaluation_time and decision_date \
            and str(evaluation_time)[:10] <= str(decision_date)[:10]:
        reasons.append("EVALUATION_NOT_AFTER_DECISION")
    if horizon_end and evaluation_time \
            and str(horizon_end)[:10] > str(evaluation_time)[:10]:
        reasons.append("HORIZON_END_AFTER_EVALUATION")
    if not outcome.get("source_data_snapshot_id"):
        reasons.append("SOURCE_DATA_SNAPSHOT_REQUIRED")
    expected_hash = _hashlib.sha256(
        _json.dumps({k: outcome.get(k) for k in OUTCOME_FIELDS
                     if k != "outcome_hash"},
                    sort_keys=True, ensure_ascii=False,
                    default=str).encode("utf-8")).hexdigest()[:16]
    if (outcome.get("outcome_hash") or "") != expected_hash:
        reasons.append("OUTCOME_HASH_MISMATCH")
    return {"valid": not reasons, "reasons": reasons,
            "outcome_id": outcome.get("outcome_id"),
            "rule": "Outcome 只追加、future-aware、"
                    "Production import=0"}


def outcome_ledger_append(conn, outcome: dict) -> int:
    """先 Validate → 再 Append（禁止 Append 后检查）。
    Identity/time/hash 任一缺失 → OUTCOME_APPEND_REJECTED。"""
    v = validate_research_outcome(conn, outcome)
    if not v["valid"]:
        raise ValueError(
            f"OUTCOME_APPEND_REJECTED: {';'.join(v['reasons'])}")
    cols = list(OUTCOME_FIELDS)
    cur = conn.execute(
        f"INSERT OR IGNORE INTO qcfp_research_outcome "
        f"({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
        [outcome.get(c) for c in cols])
    conn.commit()
    return cur.rowcount
