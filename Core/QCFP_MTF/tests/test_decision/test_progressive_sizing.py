# coding: utf-8
"""Progressive Position Sizing 测试（17 号：TEST→BUILD→CONFIRM→FULL）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.decision.retail_position_sizing import (add_requalification,
                                                      next_progressive_stage,
                                                      progressive_position_sizes,
                                                      progressive_target_position)


def test_progressive_sizes():
    sizes = progressive_position_sizes(DEFAULT_SETTINGS)
    assert sizes["TEST"] <= sizes["BUILD"] <= sizes["CONFIRM"] <= sizes["FULL"]


def test_progressive_target_monotonic():
    cur = 0.0
    for stage in ("TEST", "BUILD", "CONFIRM", "FULL"):
        nxt = progressive_target_position(stage, cur, DEFAULT_SETTINGS)
        assert nxt >= cur
        cur = nxt


def test_progressive_target_respects_cap():
    t = progressive_target_position("FULL", 0.10, DEFAULT_SETTINGS,
                                    permission_cap=0.05)
    assert t == 0.05


def test_add_requalification():
    ok, reasons = add_requalification(
        "ALLOW", 0.7, "Medium", "NORMAL", "TEST")
    assert ok and not reasons
    ok, reasons = add_requalification(
        "TEST", 0.7, "Medium", "NORMAL", "TEST")
    assert not ok and "PERMISSION_BELOW_ALLOW" in reasons
    ok, reasons = add_requalification(
        "ALLOW", 0.3, "Medium", "NORMAL", "TEST")
    assert not ok and "WAVE_BELOW_60%" in reasons
    ok, reasons = add_requalification(
        "ALLOW", 0.7, "High", "NORMAL", "TEST")
    assert not ok and "RISK_TOO_HIGH_FOR_ADD" in reasons
    ok, reasons = add_requalification(
        "ALLOW", 0.7, "Medium", "RISK_OFF", "TEST")
    assert not ok and "PORTFOLIO_RISK_OFF_BLOCKS_ADD" in reasons


def test_next_stage():
    assert next_progressive_stage("TEST", True) == "BUILD"
    assert next_progressive_stage("BUILD", True) == "CONFIRM"
    assert next_progressive_stage("CONFIRM", True) == "FULL"
    assert next_progressive_stage("FULL", True) == "FULL"
    # 未重过门 → 停档
    assert next_progressive_stage("TEST", False) == "TEST"
    # 无新确认 → 停档
    assert next_progressive_stage("BUILD", True, False) == "BUILD"
