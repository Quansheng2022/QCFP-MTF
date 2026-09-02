# coding: utf-8
"""Decision Coverage / Abstention Coverage 测试（58 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.monitoring.decision_coverage import decision_coverage, \
    decision_coverage_report


def test_coverage_distribution():
    counts = {"certified": 78, "safe_mode": 8, "abstain": 10, "halted": 4}
    r = decision_coverage(counts)
    assert r["total_decisions"] == 100
    assert r["coverage"]["certified"] == 0.78
    assert r["coverage"]["abstain"] == 0.10
    assert r["maturity_concern"] is False


def test_low_certified_triggers_concern():
    counts = {"certified": 60, "safe_mode": 5, "abstain": 30, "halted": 5}
    r = decision_coverage(counts)
    assert r["certified_ratio"] == 0.60
    assert r["maturity_concern"] is True


def test_abstain_reason_breakdown():
    counts = {"certified": 90, "safe_mode": 0, "abstain": 10, "halted": 0}
    reasons = {"pit_unknown": 4, "evidence_missing": 6,
               "permission_unavailable": 0, "liquidity_unavailable": 0,
               "replay_failure": 0}
    r = decision_coverage(counts, reasons)
    assert r["abstain_reason_breakdown"]["pit_unknown"] == 0.04
    assert r["abstain_reason_breakdown"]["evidence_missing"] == 0.06


def test_report_includes_performance_and_coverage():
    r = decision_coverage_report({"sharpe": 0.85},
                                 {"certified": 80, "safe_mode": 10,
                                  "abstain": 5, "halted": 5})
    assert "performance" in r and "coverage" in r
    assert r["reportable"] is True
