# coding: utf-8
"""绩效评估测试"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.backtest.performance import by_year, evaluate


def test_evaluate_structure():
    pnl = pd.Series([0.01, 0.02, -0.03, 0.01, 0.02])
    pos = pd.Series([1.0, 1.0, 1.0, 1.0, 1.0])
    r = evaluate(pnl, pos, annual_periods=52)
    assert r["n"] == 5
    assert r["total_return"] > 0
    assert r["max_drawdown"] < 0
    assert 0 <= r["win_rate"] <= 1
    assert r["profit_factor"] > 1


def test_sharpe_positive_for_uptrend():
    pnl = pd.Series([0.01] * 20)
    r = evaluate(pnl, annual_periods=52)
    assert r["sharpe"] > 0


def test_empty():
    r = evaluate(pd.Series(dtype=float))
    assert r["n"] == 0


def test_by_year():
    pnl = pd.Series([0.01, 0.02, -0.01])
    dates = ["2024-01-01", "2024-02-01", "2025-01-01"]
    df = by_year(pnl, dates)
    assert set(df["year"]) == {2024, 2025}


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_performance 全部通过 ✅")
