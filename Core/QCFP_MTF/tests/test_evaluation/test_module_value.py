# coding: utf-8
"""Module Value Attribution 测试（31 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.evaluation.module_value import module_net_value, \
    module_value_attribution


def _modules():
    return {
        "Permission": {"return_delta": 0.042, "mdd_delta": 0.081,
                       "sharpe_delta": 0.31, "turnover_delta": -0.12,
                       "decision_quality_delta": 0.09},
        "Regime": {"return_delta": 0.009, "mdd_delta": 0.037,
                   "sharpe_delta": 0.12, "turnover_delta": -0.02,
                   "decision_quality_delta": 0.02,
                   "complexity_cost": 0.03, "data_risk": 0.05,
                   "overfitting_risk": 0.04, "maintenance_cost": 0.02},
    }


def test_module_value_attribution():
    r = module_value_attribution(_modules())
    assert r["matrix"]["Permission"]["return_delta"] == 0.042
    assert "Permission" in r["positive_value_modules"]
    assert r["candidates_for_retirement"] == ["Regime"]


def test_module_net_value():
    v = module_net_value(0.05, 0.03, 0.02, 0.01,
                         complexity_cost=0.02, data_risk=0.01,
                         overfitting_risk=0.01, maintenance_cost=0.01)
    assert v == 0.06
    v2 = module_net_value(0.0, 0.0, 0.0, 0.0, complexity_cost=0.03)
    assert v2 < 0
