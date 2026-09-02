# coding: utf-8
"""Risk Budget Utilization Audit 测试（66 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.monitoring.risk_budget_utilization import \
    risk_budget_utilization, utilization_diagnosis


def test_low_utilization():
    r = risk_budget_utilization({"available": 1.0, "requested": 0.4,
                                 "approved": 0.25, "executed": 0.20})
    assert r["utilization"] == 0.20
    assert r["band"] == "LOW"
    assert r["unused"] == 0.80
    assert utilization_diagnosis(r)["verdict"] == "UNUSED_BUDGET"


def test_high_utilization():
    r = risk_budget_utilization({"available": 1.0, "requested": 1.0,
                                 "approved": 1.0, "executed": 0.95})
    assert r["band"] == "HIGH"
    assert utilization_diagnosis(r)["verdict"] == "CONCENTRATION_RISK"


def test_moderate_utilization():
    r = risk_budget_utilization({"available": 1.0, "requested": 0.5,
                                 "approved": 0.5, "executed": 0.5})
    assert r["band"] == "MODERATE"


def test_approved_vs_requested():
    r = risk_budget_utilization({"available": 1.0, "requested": 0.5,
                                 "approved": 0.3, "executed": 0.3})
    assert r["approved_vs_requested"] == 0.6
