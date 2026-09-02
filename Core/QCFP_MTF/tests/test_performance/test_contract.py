# coding: utf-8
"""Performance Metric Contract 测试（11 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.performance.contract import annualization_factor, \
    equity_metrics


def _returns():
    return [0.01, 0.02, -0.01, 0.03, 0.005, -0.005, 0.02, 0.01]


def test_metric_consistency():
    r1 = equity_metrics(_returns(), period="weekly")
    r2 = equity_metrics(_returns(), period="weekly")
    assert r1["sharpe"] == r2["sharpe"]
    assert r1["max_drawdown"] == r2["max_drawdown"]
    assert r1["total_return"] == r2["total_return"]


def test_metric_fields():
    r = equity_metrics(_returns(), period="weekly", rf=0.02)
    for k in ("total_return", "cagr", "annualized_vol", "sharpe",
              "sortino", "max_drawdown", "calmar", "win_rate"):
        assert k in r
    assert r["annualization"] == 52


def test_annualization_factor():
    assert annualization_factor("daily") == 252
    assert annualization_factor("weekly") == 52
    assert annualization_factor("monthly") == 12


def test_nan_handling_consistent():
    r = equity_metrics([0.01, float("nan"), 0.02], period="weekly")
    assert r["n"] == 2
