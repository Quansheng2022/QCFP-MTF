# coding: utf-8
"""Risk Reduction Attribution 测试（75 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.evaluation.risk_reduction_attribution import \
    risk_module_necessity, risk_reduction_attribution


def test_attribution_per_layer():
    r = risk_reduction_attribution({
        "Permission": {"drawdown_avoided": 0.08,
                       "tail_loss_avoided": 0.03},
        "Portfolio": {"concentration_reduced": 0.02},
        "Execution": {"turnover_cost_reduced": 0.0},
    })
    assert r["results"]["Permission"]["verdict"] == "HAS_CONTRIBUTION"
    assert r["results"]["Portfolio"]["verdict"] == "HAS_CONTRIBUTION"
    assert r["results"]["Execution"]["verdict"] == "NO_CONTRIBUTION"


def test_module_necessity():
    assert risk_module_necessity("Permission", True)["verdict"] == "KEEP"
    v = risk_module_necessity("Execution", False, other_evidence=0.03)
    assert v["verdict"] == "REVIEW"
    v2 = risk_module_necessity("Execution", False)
    assert v2["verdict"] == "SIMPLIFICATION_REVIEW"
