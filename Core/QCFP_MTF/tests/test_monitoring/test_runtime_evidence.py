# coding: utf-8
"""Runtime Evidence Artifact 硬门测试（Sprint 4 + Runtime Evidence Wiring）"""

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.monitoring.runtime_evidence import (
    build_runtime_evidence_from_ledger, continuous_certification,
    runtime_evidence_artifact, runtime_evidence_hard_gates)


def _evidence(decision=None, execution=None, reconciliation=None,
              safety=None, replay=None, outcome=None, stability=None,
              data_quality=None):
    decision = decision or {
        "expected_decisions": 10, "actual_decisions": 10, "coverage": 1.0,
        "permission_violations": 0, "uncertified_executions": 0,
        "pit_violations": 0, "safe_mode_count": 0, "halted_count": 0}
    execution = execution or {"applicable": "NOT_APPLICABLE"}
    reconciliation = reconciliation or {
        "applicable": "OPTIONAL_SIMULATION_EVIDENCE",
        "expected_reconciliations": 10, "actual_reconciliations": 10,
        "coverage": 1.0, "mismatch": 0, "unknown": 0,
        "unresolved_mismatch": 0}
    safety = safety or {
        "incident_count": 0, "recovery_count": 0, "replay_count": 0,
        "critical_replay_mismatch": 0, "reactivation_count": 0}
    replay = replay or {
        "replay_total": 10, "replay_eligible": 10, "replay_exact": 10,
        "critical_replay_mismatch": 0, "replay_status": "REPLAY_PASS"}
    outcome = outcome or {
        "outcome_count": 10, "outcome_coverage": 1.0,
        "outcome_maturity_5d": 10, "outcome_maturity_20d": 10,
        "outcome_maturity_60d": 10}
    stability = stability or {
        "decision_flip_rate": 0.0, "duplicate_decisions": 0}
    data_quality = data_quality or {"pit_grade_distribution": {"A": 10}}
    return {
        "identity": {"release_id": "REL-A"},
        "period": {"start": "2026-08-01", "end": "2026-08-28"},
        "decision": decision,
        "replay": replay,
        "outcome": outcome,
        "stability": stability,
        "data_quality": data_quality,
        "risk": {"max_drawdown": -0.1},
        "execution": execution,
        "reconciliation": reconciliation,
        "safety": safety,
        "opportunity": {"wave_candidates": 10},
    }


def test_artifact_not_proven_without_sections():
    r = runtime_evidence_artifact(identity={"release_id": "R"},
                                  period={"start": "a", "end": "b"})
    assert r["verdict"] == "NOT_PROVEN"
    assert "decision" in r["missing_sections"]


def test_artifact_ready_when_complete():
    r = runtime_evidence_artifact(**_evidence(), execution_mode="SHADOW")
    assert r["verdict"] == "DECISION_SUPPORT_EVIDENCE_READY"
    assert r["evidence_hash"]


def test_missing_required_key_not_proven():
    """第 10 项：section 存在但必填 key 缺失 → NOT_PROVEN，
    绝不能 missing → 0 → PASS。"""
    ev = _evidence()
    del ev["decision"]["coverage"]
    r = runtime_evidence_artifact(**ev, execution_mode="SHADOW")
    assert r["verdict"] == "NOT_PROVEN"
    assert "decision:coverage" in r["missing_required_keys"]
    # PAPER 缺 execution 必填 key → NOT_PROVEN
    ev2 = _evidence(execution={"applicable": "REQUIRED",
                               "order_intents": 1})
    r2 = runtime_evidence_artifact(**ev2, execution_mode="PAPER")
    assert r2["verdict"] == "NOT_PROVEN"
    assert any(k.startswith("execution:") for k in
               r2["missing_required_keys"])


def test_hard_gate_suspend():
    ev = _evidence(decision={"permission_violations": 1,
                             "uncertified_decisions": 0,
                             "pit_violations": 0})
    g = runtime_evidence_hard_gates(ev)
    assert g["state"] == "CERTIFICATION_SUSPENDED"
    assert "PERMISSION_VIOLATION" in g["suspend_reasons"]


def test_hard_gate_no_new_risk():
    ev = _evidence(execution={"applicable": "REQUIRED",
                              "order_intents": 1, "orders_sent": 1,
                              "fills": 0, "partial_fills": 0,
                              "rejects": 0, "unknown_count": 2,
                              "unresolved_unknown": 2})
    g = runtime_evidence_hard_gates(ev)
    assert g["state"] == "NO_NEW_RISK"
    assert "UNRESOLVED_BROKER_UNKNOWN" in g["no_new_risk"]


def test_continuous_certification():
    ready = runtime_evidence_artifact(**_evidence(), execution_mode="SHADOW")
    assert continuous_certification(ready) == "RENEWAL_ELIGIBLE"
    bad_decision = {
        "expected_decisions": 10, "actual_decisions": 10, "coverage": 1.0,
        "permission_violations": 1, "uncertified_executions": 0,
        "pit_violations": 0, "safe_mode_count": 0, "halted_count": 0}
    bad = runtime_evidence_artifact(
        **_evidence(decision=bad_decision),
        execution_mode="SHADOW")
    assert continuous_certification(bad) == "RENEWAL_BLOCKED"
    assert continuous_certification({"verdict": "NOT_PROVEN"}) == \
        "NOT_PROVEN"
    # 裸字符串不再是合法证据（第 10 项）
    assert continuous_certification("EVIDENCE_READY") == "NOT_PROVEN"


def test_ledger_backed_evidence():
    """第 10 项：正式证据只能由 build_runtime_evidence_from_ledger
    从真实 Ledger 构造。"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE qcfp_decision_ledger (id INTEGER PRIMARY KEY "
        "AUTOINCREMENT, decision_id TEXT, stock_code TEXT, release_id TEXT, "
        "decision_date TEXT, status TEXT, institutional_permission TEXT, "
        "final_target REAL, previous_position REAL, context TEXT, "
        "current_hash TEXT, pit_grade TEXT)")
    conn.execute(
        "INSERT INTO qcfp_decision_ledger (decision_id, stock_code, release_id, "
        "decision_date, status, institutional_permission, final_target, "
        "previous_position, context, current_hash, pit_grade) VALUES "
        "('d1','00700','REL-A','2026-08-21','ACTIVE','ALLOW',0.2,0.0,"
        "'{}','H1','A')")
    conn.execute(
        "CREATE TABLE qcfp_runtime_event_ledger (event_seq INTEGER "
        "PRIMARY KEY AUTOINCREMENT, event_id TEXT, event_type TEXT, "
        "event_time TEXT, release_id TEXT, decision_id TEXT, "
        "certificate_id TEXT, broker_order_id TEXT, "
        "reconciliation_status TEXT, current_event_hash TEXT, "
        "previous_event_hash TEXT, payload TEXT)")
    conn.execute(
        "CREATE TABLE qcfp_research_outcome (outcome_id TEXT, "
        "release_id TEXT, outcome_hash TEXT, decision_date TEXT, "
        "horizon TEXT, horizon_end TEXT)")
    conn.execute(
        "CREATE TABLE qcfp_shadow_decision_fact (fact_id TEXT, "
        "stock_code TEXT, decision_date TEXT, terminal_state TEXT)")
    conn.execute(
        "INSERT INTO qcfp_shadow_decision_fact VALUES "
        "('SF-1','00700','2026-08-21','CERTIFIED')")
    conn.execute(
        "CREATE TABLE qcfp_mtf_decision (stock_code TEXT, "
        "decision_date TEXT)")
    conn.execute("INSERT INTO qcfp_mtf_decision VALUES ('00700','2026-08-21')")
    r = build_runtime_evidence_from_ledger(
        conn, "REL-A", {"start": "2026-08-01", "end": "2026-08-28"},
        execution_mode="SHADOW",
        replay_result={"n_current_release": 1, "n_eligible": 1,
                       "n_exact": 1, "critical_mismatch": 0,
                       "status": "REPLAY_PASS",
                       "replay_hash": "H"})
    assert r["verdict"] == "DECISION_SUPPORT_EVIDENCE_READY"
    assert r["source"] == "ledger_only"
    assert r["ledger_bindings"]["decision_ledger_chain_tail"] == "H1"
    assert r["evidence"]["decision"]["actual_decisions"] == 1
    assert r["evidence"]["replay"]["replay_exact"] == 1
    assert r["evidence"]["decision"]["safe_mode_count"] == 0


def test_ledger_backed_evidence_fail_closed_without_tables():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    r = build_runtime_evidence_from_ledger(
        conn, "REL-A", {"start": "a", "end": "b"}, execution_mode="PAPER")
    assert r["verdict"] == "NOT_PROVEN"
    assert "qcfp_decision_ledger" in r["reason"]
