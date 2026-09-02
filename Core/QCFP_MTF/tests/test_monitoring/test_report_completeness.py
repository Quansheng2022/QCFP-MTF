# coding: utf-8
"""Decision Coverage 与 Performance 强制绑定测试（新 58 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.monitoring.decision_coverage import decision_coverage, \
    decision_coverage_report, report_completeness_check


def test_complete_report():
    report = decision_coverage_report(
        {"sharpe": 0.8},
        {"certified": 72, "no_trade": 16, "safe_mode": 5,
         "abstain": 6, "halted": 1})
    r = report_completeness_check(report)
    assert r["verdict"] == "COMPLETE_REPORT"
    assert r["no_trade_distinct_from_abstain"] is True


def test_incomplete_report_performance_only():
    r = report_completeness_check({"performance": {"sharpe": 0.8}})
    assert r["verdict"] == "INCOMPLETE_REPORT"
    assert "coverage" in r["missing"]


def test_incomplete_report_coverage_only():
    counts = {"certified": 90, "no_trade": 10, "safe_mode": 0,
              "abstain": 0, "halted": 0}
    r = report_completeness_check(
        {"coverage": decision_coverage(counts)})
    assert r["verdict"] == "INCOMPLETE_REPORT"
    assert "performance" in r["missing"]
