# coding: utf-8
"""Rolling Runtime Evidence Store 测试（P0-2）"""

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.monitoring.runtime_evidence_store import (
    load_runtime_evidence_window, persist_daily_runtime_evidence,
    rolling_evidence_summary)


def _artifact(verdict="EVIDENCE_READY", coverage=1.0, pit=0, perm=0,
              uncertified=0, exact=16, eligible=16, critical=0):
    return {
        "verdict": verdict,
        "evidence_hash": "H" + verdict[:2],
        "evidence": {
            "decision": {
                "actual_decisions": 16, "coverage": coverage,
                "permission_violations": perm,
                "pit_violations": pit,
                "uncertified_executions": uncertified,
            },
            "execution": {"unresolved_unknown": 0},
            "reconciliation": {"unresolved_mismatch": 0},
            "safety": {"incident_count": 0,
                       "critical_replay_mismatch": critical},
        },
    }


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def _persist(conn, date, artifact=None, mode="SHADOW"):
    return persist_daily_runtime_evidence(
        conn, artifact or _artifact(), release_id="REL-A",
        execution_mode=mode, trade_date=date, run_id=f"R-{date}",
        shadow={"universe_count": 17,
                "state_counts": {"CERTIFIED": 1, "NO_TRADE": 15,
                                 "ABSTAIN": 1, "SAFE_MODE": 0,
                                 "HALTED": 0}},
        replay={"n_eligible": 16, "n_exact": 16,
                "critical_mismatch": 0})


def test_persist_requires_verified_artifact():
    conn = _conn()
    try:
        persist_daily_runtime_evidence(
            conn, {"verdict": "EVIDENCE_READY"},
            release_id="R", execution_mode="SHADOW",
            trade_date="2026-08-21")
        raise AssertionError("should reject bare dict")
    except ValueError:
        pass
    try:
        persist_daily_runtime_evidence(
            conn, "EVIDENCE_READY", release_id="R",
            execution_mode="SHADOW", trade_date="2026-08-21")
        raise AssertionError("should reject bare string")
    except ValueError:
        pass


def test_persist_revision_and_supersede():
    conn = _conn()
    r1 = _persist(conn, "2026-08-21")
    assert r1["revision_no"] == 1
    assert r1["supersedes_evidence_id"] is None
    r2 = _persist(conn, "2026-08-21")
    assert r2["revision_no"] == 2
    assert r2["supersedes_evidence_id"] == r1["evidence_id"]
    rows = load_runtime_evidence_window(
        conn, "REL-A", "SHADOW", "2026-08-01", "2026-08-31")
    assert len(rows) == 1          # 只返回最新 revision
    assert rows[0]["revision_no"] == 2


def test_load_window_and_rolling_summary():
    conn = _conn()
    for d in ("2026-08-01", "2026-08-04", "2026-08-05"):
        _persist(conn, d)
    _persist(conn, "2026-08-06", _artifact(
        verdict="NOT_PROVEN", coverage=0.5))
    rows = load_runtime_evidence_window(
        conn, "REL-A", "SHADOW", "2026-08-01", "2026-08-31")
    s = rolling_evidence_summary(rows, window_days=4)
    assert s["qualified_days"] == 3
    assert s["not_proven_days"] == 1
    assert s["consecutive_qualified_days"] == 0
    assert s["evidence_window_hash"]
    # NOT_APPLICABLE 不中断连续天数
    rows2 = rows + [{
        "trade_date": "2026-08-07", "verdict": "NOT_APPLICABLE",
        "status": "NOT_APPLICABLE", "evidence_hash": "NA",
        "coverage": 1.0, "replay_eligible": 1, "replay_exact": 1,
        "critical_replay_mismatch": 0, "permission_violations": 0,
        "pit_violations": 0, "uncertified_executions": 0,
    }]
    s2 = rolling_evidence_summary(rows2)
    assert s2["not_applicable_days"] == 1
