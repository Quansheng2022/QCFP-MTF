# coding: utf-8
"""Risk Budget Utilization 接 Broker 测试（Release 3：新 26 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.monitoring.risk_budget_utilization import risk_budget_lineage


def test_constrained_down_explained():
    r = risk_budget_lineage({"available": 0.10, "requested": 0.08,
                             "approved": 0.05, "executed": 0.03},
                            broker_actual_risk=0.03)
    assert r["constrained_down"] is True
    assert "被 Liquidity/Portfolio 压下来" in r["explanation"]
    assert r["broker_actual"] == 0.03


def test_active_choice_explained():
    r = risk_budget_lineage({"available": 0.10, "requested": 0.04,
                             "approved": 0.04, "executed": 0.04})
    assert r["constrained_down"] is False
    assert "主动选择" in r["explanation"]
