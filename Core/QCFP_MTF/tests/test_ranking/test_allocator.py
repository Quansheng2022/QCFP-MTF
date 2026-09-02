# coding: utf-8
"""Cross-Symbol Capital Allocation 测试（45 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.ranking.allocator import allocate_capital, allocation_to_md


def test_allocation_respects_budget_and_cap():
    ranked = [{"stock_code": "A", "score": 92, "tradable": True},
              {"stock_code": "B", "score": 87, "tradable": True},
              {"stock_code": "C", "score": 81, "tradable": True},
              {"stock_code": "D", "score": 76, "tradable": True}]
    r = allocate_capital(ranked, total_budget=0.15, max_single=0.05)
    alloc = r["allocations"]
    assert alloc["A"] >= alloc["B"] >= alloc["C"]
    assert all(v <= 0.05 + 1e-9 for v in alloc.values())
    assert sum(alloc.values()) <= 0.15 + 1e-9


def test_low_score_watch():
    ranked = [{"stock_code": "A", "score": 90, "tradable": True},
              {"stock_code": "D", "score": 40, "tradable": True}]
    r = allocate_capital(ranked, total_budget=0.10, max_single=0.05,
                         watch_threshold=0.6)
    assert "D" in r["watch"]
    assert "A" in r["allocations"]


def test_allocation_to_md():
    ranked = [{"stock_code": "A", "score": 90, "tradable": True}]
    md = allocation_to_md(allocate_capital(ranked))
    assert "Capital Allocation" in md


def test_allocation_respects_permission_risk_liquidity_caps_53():
    ranked = [{"stock_code": "A", "score": 95, "tradable": True},
              {"stock_code": "B", "score": 80, "tradable": True}]
    r = allocate_capital(
        ranked, total_budget=0.20, max_single=0.10,
        permission_caps={"A": 0.06, "B": 0.08},
        risk_caps={"A": 0.05, "B": 0.10},
        liquidity_caps={"A": 0.04, "B": 0.10})
    # A 的最终分配 ≤ min(0.10, 0.06, 0.05, 0.04) = 0.04
    assert r["allocations"]["A"] <= 0.04 + 1e-9
    assert r["allocations"]["B"] <= 0.08 + 1e-9
