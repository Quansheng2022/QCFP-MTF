# coding: utf-8
"""Counterfactual Portfolio Engine 测试（47 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.ablation.portfolio_counterfactual import (counterfactual_to_md,
                                                        portfolio_counterfactual,
                                                        variant_metrics)


def _variants():
    return {
        "Actual": {"returns": [0.02, -0.01, 0.03, 0.01, -0.005, 0.02],
                   "turnover": 1.0, "mfe_capture": 0.7, "mae": -0.03,
                   "capital_utilization": 0.4},
        "No Permission": {"returns": [0.05, -0.08, 0.07, -0.06, 0.02, -0.04],
                          "turnover": 2.0, "mfe_capture": 0.9, "mae": -0.10,
                          "capital_utilization": 0.9},
        "No Wave": {"returns": [0.01, 0.0, 0.01, -0.01, 0.0, 0.01],
                    "turnover": 0.5, "mfe_capture": 0.3, "mae": -0.01,
                    "capital_utilization": 0.2},
    }


def test_variant_metrics():
    m = variant_metrics([0.02, -0.02, 0.02])
    assert "mdd" in m and "tail_loss" in m
    assert m["annualized_return"] > 0


def test_portfolio_counterfactual():
    rep = portfolio_counterfactual(_variants())
    assert rep["actual"] == "Actual"
    assert set(rep["rows"]) == {"Actual", "No Permission", "No Wave"}
    assert "No Permission" in rep["deltas"]
    # No Permission 的回撤更大 → Actual 有 Loss Avoidance Alpha
    assert rep["deltas"]["No Permission"]["loss_avoidance_alpha"] > 0
    assert rep["risk_alpha"]


def test_counterfactual_to_md():
    md = counterfactual_to_md(portfolio_counterfactual(_variants()))
    assert "Counterfactual Portfolio" in md
    assert "Risk Alpha" in md
