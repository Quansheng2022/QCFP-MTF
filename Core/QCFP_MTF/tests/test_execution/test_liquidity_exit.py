# coding: utf-8
"""Liquidity-aware Exit 测试（18 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.execution.liquidity_exit import (build_deleverage_plan,
                                               evaluate_liquidity_exit,
                                               liquidity_target_scale)


def test_liquidity_ok_small_position():
    r = evaluate_liquidity_exit(position_value=100000, adv=5000000,
                                participation=0.10, exit_required=True)
    assert r.liquidity_flag == "LIQUIDITY_OK"
    assert r.exit_days <= 1
    assert r.deleverage_plan == {}


def test_liquidity_low_large_position():
    r = evaluate_liquidity_exit(position_value=5000000, adv=5000000,
                                participation=0.10, exit_required=True,
                                start_date="2026-08-24")
    assert r.liquidity_flag == "LIQUIDITY_LOW"
    assert r.exit_days >= 10
    assert r.deleverage_plan["days"] >= 10
    assert r.deleverage_plan["end_date"]


def test_exit_not_required_no_plan():
    r = evaluate_liquidity_exit(position_value=5000000, adv=5000000,
                                participation=0.10, exit_required=False)
    assert r.liquidity_flag == "LIQUIDITY_LOW"
    assert r.deleverage_plan == {}


def test_build_deleverage_plan():
    plan = build_deleverage_plan(1000000, 2000000, 0.10, "2026-08-24", 5)
    assert plan["daily_cap"] == 200000.0
    assert plan["days"] == 5
    assert len(plan["slices"]) == 5
    assert plan["end_date"] > "2026-08-24"


def test_zero_position():
    r = evaluate_liquidity_exit(position_value=0, adv=5000000)
    assert r.liquidity_flag == "LIQUIDITY_OK"
    assert "NO_POSITION" in r.reasons


def test_liquidity_target_scale():
    ok = evaluate_liquidity_exit(position_value=100000, adv=5000000)
    fair = evaluate_liquidity_exit(position_value=400000, adv=5000000,
                                   participation=0.10)
    low = evaluate_liquidity_exit(position_value=5000000, adv=5000000,
                                  participation=0.10, exit_required=True)
    assert liquidity_target_scale(ok)["target_scale"] == 1.0
    assert liquidity_target_scale(fair)["target_scale"] == 0.7
    assert liquidity_target_scale(low)["target_scale"] == 0.0
    r = liquidity_target_scale(fair, target=0.2)
    assert r["compressed_target"] == 0.14
