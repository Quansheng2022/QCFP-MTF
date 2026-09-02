# coding: utf-8
"""Rolling Runtime Evidence Store（P0-2）

把"单日 Runtime Evidence artifact"升级为可查询的滚动证据投影：
    qcfp_runtime_evidence_daily

本模块只做 persistence/projection：
    persist_daily_runtime_evidence()
    load_runtime_evidence_window()
    rolling_evidence_summary()

绝对不允许出现：
    decide_target() / change_permission() / promote_release()

正式证据只能来自 build_runtime_evidence_from_ledger() 构造的
verified artifact（dict 且带 evidence_hash）；本模块不产生任何
决策/权限/目标结论。

唯一键：(release_id, execution_mode, trade_date)。
同一天重跑不静默覆盖 → revision_no 递增 + supersedes_evidence_id。
"""

import hashlib
import json
from datetime import datetime


RUNTIME_EVIDENCE_DAILY_DDL = """
CREATE TABLE IF NOT EXISTS qcfp_runtime_evidence_daily (
    evidence_id TEXT PRIMARY KEY,
    release_id TEXT NOT NULL,
    execution_mode TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    run_id TEXT,
    revision_no INTEGER NOT NULL DEFAULT 1,
    supersedes_evidence_id TEXT,
    universe_count INTEGER,
    actual_decisions INTEGER,
    coverage REAL,
    certified_count INTEGER,
    no_trade_count INTEGER,
    abstain_count INTEGER,
    safe_mode_count INTEGER,
    halted_count INTEGER,
    permission_violations INTEGER,
    pit_violations INTEGER,
    uncertified_executions INTEGER,
    replay_eligible INTEGER,
    replay_exact INTEGER,
    critical_replay_mismatch INTEGER,
    incident_count INTEGER,
    unresolved_unknown INTEGER,
    unresolved_mismatch INTEGER,
    evidence_hash TEXT,
    verdict TEXT,
    evidence_freeze_id TEXT,
    feature_manifest_hash TEXT,
    config_hash TEXT,
    universe_hash TEXT,
    decision_duplicate_count INTEGER,
    outcome_count INTEGER,
    outcome_coverage REAL,
    outcome_maturity_5d INTEGER,
    outcome_maturity_20d INTEGER,
    outcome_maturity_60d INTEGER,
    decision_flip_rate REAL,
    daily_evidence_state TEXT,
    qualification_eligible INTEGER,
    invalidated INTEGER DEFAULT 0,
    invalidation_reason TEXT,
    created_at TEXT,
    UNIQUE (release_id, execution_mode, trade_date, revision_no)
)
"""


def ensure_runtime_evidence_daily_table(conn) -> None:
    """显式建表（测试/本地）。Production schema 由 SQL 迁移拥有。"""
    conn.execute(RUNTIME_EVIDENCE_DAILY_DDL)


EVIDENCE_DAILY_UPGRADE_COLUMNS = {
    "evidence_freeze_id": "TEXT",
    "feature_manifest_hash": "TEXT",
    "config_hash": "TEXT",
    "universe_hash": "TEXT",
    "decision_duplicate_count": "INTEGER",
    "outcome_count": "INTEGER",
    "outcome_coverage": "REAL",
    "outcome_maturity_5d": "INTEGER",
    "outcome_maturity_20d": "INTEGER",
    "outcome_maturity_60d": "INTEGER",
    "decision_flip_rate": "REAL",
    "daily_evidence_state": "TEXT",
    "qualification_eligible": "INTEGER",
    "invalidated": "INTEGER DEFAULT 0",
    "invalidation_reason": "TEXT",
}


def upgrade_runtime_evidence_daily_schema(conn) -> list:
    """幂等补齐新列（迁移工具调用；真实库由 SQL migration 拥有）。"""
    cols = {r["name"] for r in conn.execute(
        "PRAGMA table_info(qcfp_runtime_evidence_daily)").fetchall()}
    added = []
    for name, ddl in EVIDENCE_DAILY_UPGRADE_COLUMNS.items():
        if name not in cols:
            conn.execute(
                f"ALTER TABLE qcfp_runtime_evidence_daily "
                f"ADD COLUMN {name} {ddl}")
            added.append(name)
    if added:
        conn.commit()
    return added


def persist_daily_runtime_evidence(conn, evidence_artifact, *,
                                   release_id, execution_mode, trade_date,
                                   run_id="", shadow=None, replay=None,
                                   outcome=None, stability=None,
                                   freeze=None, daily_gate=None,
                                   created_at=None) -> dict:
    """持久化单日 Evidence projection（append-only + revision）。

    evidence_artifact 必须是 build_runtime_evidence_from_ledger()
    输出的 dict（带 verdict + evidence_hash）；裸字符串 / 无 hash
    的 dict 一律拒绝——不能调用方"告诉系统自己没问题"。
    """
    if not isinstance(evidence_artifact, dict) \
            or not evidence_artifact.get("evidence_hash"):
        raise ValueError(
            "runtime evidence 必须来自 verified artifact "
            "（dict 且带 evidence_hash），禁止裸数据自证")
    ensure_runtime_evidence_daily_table(conn)
    mode = str(execution_mode or "").upper()
    prev = conn.execute(
        "SELECT evidence_id, MAX(revision_no) AS rev "
        "FROM qcfp_runtime_evidence_daily "
        "WHERE release_id=? AND execution_mode=? AND trade_date=? "
        "GROUP BY release_id, execution_mode, trade_date",
        (release_id, mode, trade_date)).fetchone()
    revision = int(prev["rev"]) + 1 if prev and prev["rev"] else 1
    supersedes = prev["evidence_id"] if prev else None
    evidence_id = (f"RE-{release_id}-{mode}-{trade_date}-"
                   f"r{revision}")
    shadow = shadow or {}
    replay = replay or {}
    decision = (evidence_artifact.get("evidence") or {}).get(
        "decision") or {}
    execution = (evidence_artifact.get("evidence") or {}).get(
        "execution") or {}
    reconciliation = (evidence_artifact.get("evidence") or {}).get(
        "reconciliation") or {}
    safety = (evidence_artifact.get("evidence") or {}).get(
        "safety") or {}
    outcome = outcome or (evidence_artifact.get("evidence") or {}).get(
        "outcome") or {}
    stability = stability or (evidence_artifact.get("evidence") or {}
                              ).get("stability") or {}
    freeze = freeze or {}
    gate = daily_gate or {}
    invalidated = 1 if gate.get("state") == "DAILY_EVIDENCE_INVALID" else 0
    invalidation_reason = ";".join(
        gate.get("invalid_reasons") or []) if invalidated else ""
    conn.execute(
        "INSERT OR REPLACE INTO qcfp_runtime_evidence_daily "
        "(evidence_id, release_id, execution_mode, trade_date, run_id, "
        "revision_no, supersedes_evidence_id, universe_count, "
        "actual_decisions, coverage, certified_count, no_trade_count, "
        "abstain_count, safe_mode_count, halted_count, "
        "permission_violations, pit_violations, uncertified_executions, "
        "replay_eligible, replay_exact, critical_replay_mismatch, "
        "incident_count, unresolved_unknown, unresolved_mismatch, "
        "evidence_hash, verdict, evidence_freeze_id, "
        "feature_manifest_hash, config_hash, universe_hash, "
        "decision_duplicate_count, outcome_count, outcome_coverage, "
        "outcome_maturity_5d, outcome_maturity_20d, outcome_maturity_60d, "
        "decision_flip_rate, daily_evidence_state, "
        "qualification_eligible, invalidated, invalidation_reason, "
        "created_at) VALUES (?,?,?,?,?,?,?,?,?,?,"
        "?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (evidence_id, release_id, mode, trade_date, run_id,
         revision, supersedes,
         int(shadow.get("universe_count") or 0),
         int(decision.get("actual_decisions") or 0),
         float(decision.get("coverage") or 0.0),
         int((shadow.get("state_counts") or {}).get("CERTIFIED") or 0),
         int((shadow.get("state_counts") or {}).get("NO_TRADE") or 0),
         int((shadow.get("state_counts") or {}).get("ABSTAIN") or 0),
         int((shadow.get("state_counts") or {}).get("SAFE_MODE") or 0),
         int((shadow.get("state_counts") or {}).get("HALTED") or 0),
         int(decision.get("permission_violations") or 0),
         int(decision.get("pit_violations") or 0),
         int(decision.get("uncertified_executions") or 0),
         int(replay.get("n_eligible") or 0),
         int(replay.get("n_exact") or 0),
         int(replay.get("critical_mismatch") or 0),
         int(safety.get("incident_count") or 0),
         int(execution.get("unresolved_unknown") or 0),
         int(reconciliation.get("unresolved_mismatch") or 0),
         evidence_artifact.get("evidence_hash"),
         evidence_artifact.get("verdict"),
         freeze.get("evidence_freeze_id") or "",
         freeze.get("feature_manifest_hash") or "",
         freeze.get("config_hash") or "",
         freeze.get("universe_definition_hash") or "",
         int(stability.get("duplicate_decisions") or 0),
         int(outcome.get("outcome_count") or 0),
         float(outcome.get("outcome_coverage") or 0.0),
         int(outcome.get("outcome_maturity_5d") or 0),
         int(outcome.get("outcome_maturity_20d") or 0),
         int(outcome.get("outcome_maturity_60d") or 0),
         float(stability.get("decision_flip_rate") or 0.0),
         gate.get("state") or "",
         1 if gate.get("qualified") else 0,
         invalidated,
         invalidation_reason,
         created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    return {"evidence_id": evidence_id, "revision_no": revision,
            "supersedes_evidence_id": supersedes,
            "verdict": evidence_artifact.get("verdict")}


def load_runtime_evidence_window(conn, release_id, execution_mode,
                                 start, end) -> list:
    """最近窗口（含端点）：每个 (release, mode, date) 只取最新 revision。"""
    ensure_runtime_evidence_daily_table(conn)
    rows = conn.execute(
        "SELECT e.* FROM qcfp_runtime_evidence_daily e "
        "WHERE e.release_id=? AND e.execution_mode=? "
        "AND e.trade_date>=? AND e.trade_date<=? "
        "AND e.revision_no=(SELECT MAX(x.revision_no) "
        "FROM qcfp_runtime_evidence_daily x "
        "WHERE x.release_id=e.release_id AND x.execution_mode="
        "e.execution_mode AND x.trade_date=e.trade_date) "
        "ORDER BY e.trade_date",
        (release_id, str(execution_mode).upper(), start, end)).fetchall()
    return [dict(r) for r in rows]


def _day_qualified(day: dict) -> tuple:
    """单日是否构成合格证据（与 Promotion Gate 同一口径，薄投影）。"""
    from ..governance.runtime_promotion_gate import day_qualified
    return day_qualified(day)


def rolling_evidence_summary(rows, window_days=None,
                             required_days=20) -> dict:
    """滚动汇总：qualified / failed / not_proven / suspended /
    consecutive_qualified_days（可直接回答 Last 5/20/60）。"""
    rows = list(rows or [])
    if window_days is not None:
        rows = rows[-int(window_days):]
    qualified_days = 0
    failed_days = 0
    not_proven_days = 0
    suspended_days = 0
    not_applicable_days = 0
    consecutive_qualified = 0
    blocking_reasons = []
    window_parts = []
    for day in rows:
        window_parts.append(
            f"{day.get('trade_date')}|{day.get('verdict')}|"
            f"{day.get('evidence_hash')}")
        if str(day.get("status") or "").upper() == "NOT_APPLICABLE":
            not_applicable_days += 1
            continue
        verdict = str(day.get("verdict") or "").upper()
        if verdict in ("CERTIFICATION_SUSPENDED", "NO_NEW_RISK"):
            suspended_days += 1
            consecutive_qualified = 0
            blocking_reasons.append(
                f"{day.get('trade_date')}:{verdict}")
            continue
        if verdict == "NOT_PROVEN":
            not_proven_days += 1
            consecutive_qualified = 0
            continue
        ok, reasons = _day_qualified(day)
        if ok:
            qualified_days += 1
            consecutive_qualified += 1
        else:
            failed_days += 1
            consecutive_qualified = 0
            blocking_reasons.extend(
                f"{day.get('trade_date')}:{r}" for r in reasons[:3])
    window_hash = hashlib.sha256(
        "\n".join(window_parts).encode("utf-8")).hexdigest()[:16] \
        if window_parts else ""
    return {
        "window_days": len(rows),
        "qualified_days": qualified_days,
        "failed_days": failed_days,
        "not_proven_days": not_proven_days,
        "suspended_days": suspended_days,
        "not_applicable_days": not_applicable_days,
        "consecutive_qualified_days": consecutive_qualified,
        "required_days": required_days,
        "remaining_days": max(0, required_days - consecutive_qualified),
        "blocking_reasons": blocking_reasons[:10],
        "evidence_window_hash": window_hash,
                "rule": "只读 Evidence projection；连续合格天数被任何 "
                        "FAIL/SUSPEND/NOT_PROVEN 中断；NOT_APPLICABLE "
                        "（休市/维护）不计入也不中断",
    }


def rolling_windows_summary(rows, required_days=20) -> dict:
    """5D warm-up / 20D qualification / 60D observation / 120D health。"""
    return {
        "5d": rolling_evidence_summary(rows, window_days=5,
                                       required_days=required_days),
        "20d": rolling_evidence_summary(rows, window_days=20,
                                        required_days=required_days),
        "60d": rolling_evidence_summary(rows, window_days=60,
                                        required_days=required_days),
        "120d": rolling_evidence_summary(rows, window_days=120,
                                         required_days=required_days),
    }


def outcome_qualified_days(rows, outcome_min_coverage=0.8) -> dict:
    """Outcome 合格天数：outcome 记录存在 + 5D 成熟度 > 0 + 覆盖达标。"""
    rows = list(rows or [])
    ok = 0
    for day in rows:
        if str(day.get("status") or "").upper() == "NOT_APPLICABLE":
            continue
        if str(day.get("verdict") or "").upper() not in (
                "EVIDENCE_READY", "DECISION_SUPPORT_EVIDENCE_READY"):
            continue
        matured_5d = int(day.get("outcome_maturity_5d") or 0)
        coverage = float(day.get("outcome_coverage") or 0.0)
        if matured_5d > 0 and coverage >= outcome_min_coverage - 1e-9:
            ok += 1
    return {"outcome_qualified_days": ok,
            "required_days": 20,
            "remaining_days": max(0, 20 - ok)}
