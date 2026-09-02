# coding: utf-8
"""Execution Simulator 全流水线测试（27 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.execution.simulator import (executable_target,
                                          return_decomposition,
                                          simulate_execution)


def test_full_fill_base():
    r = simulate_execution(order_amount=100000, adv_amount=5000000)
    assert r["fill_pct"] == 1.0
    assert r["executable"] is True
    assert r["filled_amount"] == 100000.0
    assert r["reasons"] == ["FULL_FILL"]


def test_partial_fill_low_liquidity():
    r = simulate_execution(order_amount=5000000, adv_amount=5000000,
                           participation_rate=0.10, fill_rate=1.0)
    assert r["fill_pct"] == 0.1
    assert r["executable"] is True
    assert "PARTIAL_FILL" in r["reasons"]
    assert len(r["batches"]) > 1


def test_suspended_and_limit():
    assert simulate_execution(100000, 5000000,
                              suspended=True)["executable"] is False
    assert simulate_execution(100000, 5000000,
                              limit_up=True)["executable"] is False
    assert simulate_execution(100000, 5000000,
                              limit_down=True)["executable"] is False


def test_extra_cost_bps():
    r = simulate_execution(100000, 5000000, spread_bps=10, slippage_bps=5)
    assert r["avg_extra_cost_bps"] >= 15.0


def test_return_decomposition():
    d = return_decomposition(signal_return=0.20, gross_return=0.19,
                             execution_return=0.185, net_return=0.18)
    assert d["signal_return"] == 0.20
    assert d["net_return"] == 0.18
    assert d["execution_cost_impact"] == 0.005
    assert d["total_friction"] == 0.01


def test_gap_and_fill_basis():
    r = simulate_execution(100000, 5000000, gap_bps=30.0,
                           fill_price_basis="open")
    assert r["gap_bps"] == 30.0
    assert r["fill_price_basis"] == "open"
    r2 = simulate_execution(100000, 5000000, gap_bps=0.0)
    assert r2["avg_extra_cost_bps"] < r["avg_extra_cost_bps"]


def test_executable_target_17():
    r = executable_target(target=0.50, capital=1_000_000, adv=1_000_000,
                          participation_rate=0.10)
    assert r["executable_target"] < 0.50
    assert r["reduced"] is True
    r2 = executable_target(target=0.01, capital=1_000_000, adv=1_000_000,
                           participation_rate=0.10)
    assert r2["reduced"] is False
