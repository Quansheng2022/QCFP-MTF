# coding: utf-8
"""Regime-conditioned Decision 测试（13 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.market.regime_conditioned import (regime_adjusted_permission,
                                                regime_conditioned_modifiers)


def test_regime_modifiers():
    bull = regime_conditioned_modifiers("Bull")
    crisis = regime_conditioned_modifiers("Crisis")
    assert bull["risk_budget_scale"] == 1.0
    assert crisis["risk_budget_scale"] < bull["risk_budget_scale"]
    assert crisis["wave_threshold_up"] > bull["wave_threshold_up"]
    assert crisis["permission_never_raised"] is True


def test_regime_never_raises_permission():
    r = regime_adjusted_permission("ALLOW", "Crisis")
    assert r["adjusted_strength_leq_base"] is True
    assert r["adjusted_strength"] < r["base_strength"]
    r2 = regime_adjusted_permission("ALLOW", "Bull")
    assert r2["adjusted_strength"] <= r2["base_strength"] + 1e-9
