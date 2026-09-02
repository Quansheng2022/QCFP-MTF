# coding: utf-8
"""Runtime Closure Report 测试（C2/C3 产物）"""

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.monitoring.runtime_evidence_store import \
    persist_daily_runtime_evidence
from QCFP_MTF.scripts.runtime_closure_report import build_closure_report


def _artifact():
    return {
        "verdict": "EVIDENCE_READY", "evidence_hash": "H1",
        "evidence": {
            "decision": {"actual_decisions": 16, "coverage": 1.0,
                         "permission_violations": 0,
                         "pit_violations": 0,
                         "uncertified_executions": 0},
            "execution": {"unresolved_unknown": 0},
            "reconciliation": {"unresolved_mismatch": 0},
            "safety": {"incident_count": 0,
                       "critical_replay_mismatch": 0}}}


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def test_closure_report_accumulating_with_one_day():
    conn = _conn()
    persist_daily_runtime_evidence(
        conn, _artifact(), release_id="REL-A", execution_mode="SHADOW",
        trade_date="2026-08-21", run_id="R1",
        shadow={"universe_count": 17,
                "state_counts": {"CERTIFIED": 1, "NO_TRADE": 15,
                                 "ABSTAIN": 1, "SAFE_MODE": 0,
                                 "HALTED": 0}},
        replay={"n_eligible": 16, "n_exact": 16,
                "critical_mismatch": 0})
    report = build_closure_report(conn, "REL-A", "SHADOW",
                                  required_days=20)
    q = report["qualification"]
    assert q["state"] == "SHADOW_ACCUMULATING"
    assert q["qualified_days"] == 1
    assert q["remaining_days"] == 19
    assert q["hard_reset_count"] == 0
    assert q["evidence_window_hash"]
    dist = report["terminal_state_distribution"]
    assert dist["total"] == 17
    assert dist["certified_pct"] == round(100.0 * 1 / 17, 2)
    assert report["replay_summary"]["total_exact"] == 16
    conn.close()


def test_closure_report_empty_window():
    conn = _conn()
    report = build_closure_report(conn, "REL-A", "SHADOW",
                                  required_days=20)
    assert report["qualification"]["state"] == "SHADOW_ACCUMULATING"
    assert report["qualification"]["qualified_days"] == 0
    assert report["terminal_state_distribution"]["total"] == 0
    conn.close()
