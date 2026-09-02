# coding: utf-8
"""Regime Robustness / Transition 测试（38 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.market.regime_robustness import regime_robustness_report, \
    regime_state


def test_regime_state_stable():
    r = regime_state("Market", 0.05)
    assert r.state == "REGIME_STABLE"
    assert r.permission_scale == 1.0


def test_regime_state_transition_tightens():
    r = regime_state("Market", 0.6)
    assert r.state == "REGIME_TRANSITION"
    assert r.permission_scale < 1.0


def test_regime_state_uncertain_bear():
    r = regime_state("Bear", 0.4, unstable_regimes=("Bear",))
    assert r.state == "REGIME_UNCERTAIN"
    assert r.permission_scale == 0.7


def test_regime_robustness_report():
    rep = regime_robustness_report({
        "Market": 0.05, "Institutional": 0.1,
        "Volatility": 0.6, "Liquidity": 0.2, "Trend": 0.05})
    assert "transition_regimes" in rep
    assert rep["overall_permission_scale"] < 1.0
    assert rep["tightened"] is True
