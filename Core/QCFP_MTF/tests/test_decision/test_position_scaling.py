# coding: utf-8
"""Position Scaling Policy 测试（76 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.position_scaling import position_scaling_policy


def test_scaling_lifecycle():
    confirming = position_scaling_policy("CONFIRMING")
    active = position_scaling_policy("ACTIVE")
    mature = position_scaling_policy("MATURE")
    assert confirming.final_position < active.final_position
    assert mature.final_position > active.final_position
    assert position_scaling_policy("INVALID").final_position == 0.0


def test_signal_risk_modulation():
    expand = position_scaling_policy("ACTIVE", signal_trend=1.5,
                                     risk_trend=0.5)
    contract = position_scaling_policy("ACTIVE", signal_trend=0.5,
                                       risk_trend=2.0)
    assert expand.final_position > contract.final_position


def test_governance_caps_bound():
    r = position_scaling_policy("MATURE", signal_trend=3.0,
                                risk_trend=0.5, liquidity_cap=0.02)
    assert r.final_position <= 0.02 + 1e-9
    assert r.capped is True
    assert any("GOVERNANCE_CAP_BOUND" in x for x in r.reasons)
