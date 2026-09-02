# coding: utf-8
"""Strategy Capacity Engine 测试（35 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.execution.capacity import (alpha_capacity, capacity_cap_target,
                                         strategy_capacity)


def test_strategy_capacity_levels():
    c = strategy_capacity(adv=100_000_000)
    assert len(c["rows"]) == 4
    rates = [r["participation"] for r in c["rows"]]
    assert rates == [0.01, 0.03, 0.05, 0.10]
    caps = [r["capacity"] for r in c["rows"]]
    assert caps[0] < caps[-1]
    assert c["summary"]["1%"] == "Efficient"


def test_strategy_capacity_turnover_penalty():
    c1 = strategy_capacity(adv=100_000_000, turnover=1.0)
    c2 = strategy_capacity(adv=100_000_000, turnover=2.0)
    assert c2["efficient_capacity"] < c1["efficient_capacity"]


def test_strategy_capacity_degraded():
    c = strategy_capacity(adv=10_000_000, turnover=5.0)
    assert any(r["band"] != "Efficient" for r in c["rows"])


def test_capacity_cap_target():
    # 大仓位超单日容量 → 压缩
    r = capacity_cap_target(target=0.50, capital=1_000_000, adv=1_000_000,
                            participation=0.10)
    assert r["capped"] is True
    assert r["target"] < 0.50
    # 小仓位在容量内 → 不变
    r2 = capacity_cap_target(target=0.01, capital=1_000_000, adv=1_000_000,
                             participation=0.10)
    assert r2["capped"] is False
    assert r2["target"] == 0.01


def test_alpha_capacity_decay_79():
    r = alpha_capacity(adv=50_000_000,
                       capital_levels=(100_000, 1_000_000, 5_000_000,
                                       10_000_000),
                       base_sharpe=1.8)
    assert r["rows"][0]["sharpe"] == 1.8
    assert r["rows"][-1]["sharpe"] < r["rows"][0]["sharpe"]
    assert r["rows"][-1]["decay_vs_base"] < 1.0
    assert r["max_efficient_capital"] > 0
