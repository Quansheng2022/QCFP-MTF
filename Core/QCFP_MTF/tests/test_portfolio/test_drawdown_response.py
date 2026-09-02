# coding: utf-8
"""Drawdown Response Engine 测试（44 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.portfolio.drawdown_response import (apply_drawdown_gate,
                                                  drawdown_response,
                                                  drawdown_state)


def test_drawdown_state_bands():
    assert drawdown_state(0.01) == "NORMAL"
    assert drawdown_state(0.04) == "CAUTION"
    assert drawdown_state(0.06) == "DEFENSIVE"
    assert drawdown_state(0.10) == "SAFE_MODE"


def test_response_monotonic_risk_reduction():
    r1 = drawdown_response(0.02)
    r2 = drawdown_response(0.04)
    r3 = drawdown_response(0.06)
    r4 = drawdown_response(0.10)
    assert r1.new_entry_cap_scale > r2.new_entry_cap_scale > \
        r3.new_entry_cap_scale > r4.new_entry_cap_scale
    assert r1.risk_budget_scale > r4.risk_budget_scale
    assert r1.exit_threshold_scale < r4.exit_threshold_scale


def test_safe_mode_blocks_new_risk():
    r = apply_drawdown_gate(0.10, target=0.3, previous_position=0.0)
    assert r["response"]["state"] == "SAFE_MODE"
    assert r["target"] == 0.0
    assert r["cash_ratio_floor"] == 0.7


def test_normal_no_restriction():
    r = apply_drawdown_gate(0.01, target=0.2, previous_position=0.0)
    assert r["target"] == 0.2
