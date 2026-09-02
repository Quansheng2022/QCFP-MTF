# coding: utf-8
"""Regime Transition State Machine 测试（86 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.market.regime_fsm import REGIME_FSM_STATES, \
    apply_regime_transition, regime_transition


def test_bull_to_bear_chain():
    t1 = regime_transition("BULL_STABLE", "BULL_WEAKENING")
    t2 = regime_transition("BULL_WEAKENING", "TRANSITION")
    t3 = regime_transition("TRANSITION", "BEAR_CONFIRMING")
    t4 = regime_transition("BEAR_CONFIRMING", "BEAR_STABLE")
    assert t1.permission_effect > t4.permission_effect
    assert t1.entry_threshold_up < t4.entry_threshold_up


def test_bear_to_bull_recovery():
    t1 = regime_transition("BEAR_STABLE", "RECOVERY")
    t2 = regime_transition("RECOVERY", "TRANSITION")
    t3 = regime_transition("TRANSITION", "BULL_CONFIRMING")
    assert t3.permission_effect > t1.permission_effect


def test_illegal_transition_rejected():
    try:
        regime_transition("BULL_STABLE", "BEAR_STABLE")
        raise AssertionError("should raise")
    except ValueError:
        pass


def test_apply_transition():
    t = regime_transition("BULL_WEAKENING", "TRANSITION")
    r = apply_regime_transition(0.10, t)
    assert r["target"] < 0.10
    assert r["permission_scale"] == t.permission_effect


def test_states_constant():
    assert "TRANSITION" in REGIME_FSM_STATES
    assert "BULL_WEAKENING" in REGIME_FSM_STATES
