# coding: utf-8
"""Risk Contagion Engine 测试（34 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

import numpy as np

from QCFP_MTF.portfolio.risk_contagion import (cluster_stress,
                                               conditional_loss,
                                               contagion_cap_scale,
                                               liquidity_contagion,
                                               marginal_and_component_var,
                                               portfolio_var,
                                               risk_contagion_report)


def _cov():
    return [[0.04, 0.01], [0.01, 0.09]]


def test_portfolio_var():
    v = portfolio_var([0.5, 0.5], _cov())
    assert v > 0


def test_marginal_component_var():
    mc = marginal_and_component_var([0.5, 0.5], _cov())
    assert len(mc["marginal_var"]) == 2
    assert abs(mc["total_component_var"] - portfolio_var([0.5, 0.5],
                                                         _cov())) < 1e-4


def test_conditional_loss():
    r = np.array([[0.01, 0.02], [-0.05, -0.03], [0.03, 0.01],
                  [-0.08, -0.05]])
    cv = conditional_loss(r, [0.5, 0.5], q=0.25)
    assert cv > 0


def test_cluster_stress():
    cl = cluster_stress([["A", "B"], ["C"]], {0: -0.10, 1: -0.05},
                        {"A": 0.3, "B": 0.3, "C": 0.4})
    assert "cluster_0" in cl
    assert cl["cluster_0"]["loss_contribution"] > 0


def test_liquidity_contagion():
    pos = [{"stock_code": "A", "exit_days": 5},
           {"stock_code": "B", "exit_days": 1}]
    adv = {"A": 100, "B": 5000}
    corr = {"A": {"B": 0.85}, "B": {"A": 0.85}}
    lq = liquidity_contagion(pos, adv, corr_matrix=corr)
    assert lq["illiquid_positions"] == ["A"]
    assert lq["liquidity_contagion_risk"] is True


def test_contagion_cap_scale():
    scale = contagion_cap_scale({0: 0.04, 1: 0.03}, risk_budget=0.05)
    assert 0 <= scale < 0.5
    assert contagion_cap_scale({}, 0.05) == 1.0


def test_risk_contagion_report():
    rep = risk_contagion_report([0.5, 0.5], _cov(),
                                returns_matrix=np.array(
                                    [[0.01, 0.02], [-0.05, -0.03]]),
                                positions=[{"stock_code": "A",
                                            "weight": 0.5},
                                           {"stock_code": "B",
                                            "weight": 0.5}],
                                adv_map={"A": 100, "B": 5000},
                                risk_budget=0.05)
    assert "portfolio_var95" in rep
    assert "position_cap_scale" in rep
