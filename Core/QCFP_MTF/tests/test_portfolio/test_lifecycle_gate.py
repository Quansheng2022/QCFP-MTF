# coding: utf-8
"""Portfolio Lifecycle Gate 测试（21 号：组合状态作用于全生命周期）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.portfolio.lifecycle_gate import (ACTIONS, apply_lifecycle_gate,
                                               portfolio_action_gate)
from QCFP_MTF.portfolio.state_engine import portfolio_state, \
    state_constraints


def test_state_engine_basic():
    assert portfolio_state({"total_exposure": 0.5, "cash_ratio": 0.3}) == \
        "NORMAL"
    assert portfolio_state({"permission_risk_share": 0.7}) == "RISK_OFF"
    assert portfolio_state({"sector_concentration": 0.6}) == "CONCENTRATED"
    assert portfolio_state({"total_exposure": 0.9, "market_vol": 0.4,
                            "cash_ratio": 0.05}) == "OVERHEATED"
    assert portfolio_state({"mdd_recent": 0.15}) == "DEFENSIVE"


def test_state_constraints():
    c = state_constraints("RISK_OFF")
    assert c["add_allowed"] is False
    assert c["prioritize_reduce"] is True


def test_lifecycle_gate_blocks_risk_off():
    for action in ("ENTRY", "ADD"):
        g = portfolio_action_gate("RISK_OFF", action)
        assert g.allowed is False
        assert g.action == action
    assert portfolio_action_gate("RISK_OFF", "REDUCE").allowed is True
    assert portfolio_action_gate("RISK_OFF", "EXIT").allowed is True


def test_lifecycle_gate_concentrated_add():
    g = portfolio_action_gate("CONCENTRATED", "ADD",
                              concentration_add_ok=False)
    assert g.allowed is False
    assert "CONCENTRATED_ADD_NEEDS_DIVERSIFICATION" in g.reasons
    g2 = portfolio_action_gate("CONCENTRATED", "ADD",
                               concentration_add_ok=True)
    assert g2.allowed is True


def test_apply_lifecycle_gate_target():
    r = apply_lifecycle_gate("RISK_OFF", 0.3, 0.0, "ENTRY")
    assert r["target"] == 0.0
    r = apply_lifecycle_gate("DEFENSIVE", 0.2, 0.0, "ENTRY",
                             cap_scale_input=0.7)
    assert r["target"] == 0.14
    r = apply_lifecycle_gate("OVERHEATED", 0.3, 0.2, "EXIT")
    assert r["target"] == 0.2


def test_actions_constant():
    assert ACTIONS == ("ENTRY", "ADD", "HOLD", "REDUCE", "EXIT")
