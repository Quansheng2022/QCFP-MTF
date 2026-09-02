# coding: utf-8
"""Risk Budget Utilization 资金效率报告测试（新 66 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.monitoring.risk_budget_utilization import risk_efficiency_report


def test_report_shows_all_risk_buckets():
    r = risk_efficiency_report({"available": 0.10, "requested": 0.08,
                                "approved": 0.05, "executed": 0.02})
    assert r["available_risk"] == 0.10
    assert r["approved_risk"] == 0.05
    assert r["executed_risk"] == 0.02
    assert r["unused_risk"] == 0.08
    assert r["band"] == "LOW"


def test_report_rule():
    r = risk_efficiency_report({"available": 1.0, "requested": 1.0,
                                "approved": 1.0, "executed": 0.95})
    assert "而不是只有仓位百分比" in r["report_rule"]
    assert r["band"] == "HIGH"
