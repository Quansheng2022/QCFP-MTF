# coding: utf-8
"""Strategy Capacity Allocation 测试（88 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.portfolio.strategy_allocation import strategy_allocation


def _strategies():
    return {
        "wave": {"score": 0.9, "capacity": 0.8, "drawdown": 0.2,
                 "confidence": 0.8, "cost": 0.1},
        "breakout": {"score": 0.6, "capacity": 0.6, "drawdown": 0.4,
                     "confidence": 0.6, "cost": 0.2},
        "entry": {"score": 0.5, "capacity": 0.5, "drawdown": 0.5,
                  "confidence": 0.5, "cost": 0.3},
    }


def test_allocation_respects_budget_and_cap():
    r = strategy_allocation(_strategies(), total_risk_budget=0.10,
                            max_per_strategy=0.05)
    total = sum(r.allocations.values())
    assert total <= 0.10 + 1e-9
    assert all(v <= 0.05 + 1e-9 for v in r.allocations.values())
    # 高分策略获得更多
    assert r.allocations["wave"] >= r.allocations["entry"]


def test_governance_cap_marks():
    r = strategy_allocation(_strategies(), total_risk_budget=0.10,
                            portfolio_risk_cap=0.03)
    assert r.governance_capped is True
    assert all(v <= 0.03 + 1e-9 for v in r.allocations.values())
