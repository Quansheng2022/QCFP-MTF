# coding: utf-8
"""OOS Summary 测试（26 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

import pandas as pd

from QCFP_MTF.backtest.cross_validation import oos_summary


def test_oos_summary_consistent():
    df = pd.DataFrame([
        {"window": "W1", "annualized_return": 0.10, "sharpe": 1.0,
         "max_drawdown": -0.08, "avg_turnover": 1.2, "win_rate": 0.55},
        {"window": "W2", "annualized_return": 0.08, "sharpe": 0.8,
         "max_drawdown": -0.09, "avg_turnover": 1.1, "win_rate": 0.52},
        {"window": "W3", "annualized_return": 0.05, "sharpe": 0.6,
         "max_drawdown": -0.10, "avg_turnover": 1.0, "win_rate": 0.50},
    ])
    s = oos_summary(df)
    assert s["n_windows"] == 3
    assert s["positive_window_ratio"] == 1.0
    assert s["consistent"] is True


def test_oos_summary_inconsistent():
    df = pd.DataFrame([
        {"window": "W1", "annualized_return": 0.12, "sharpe": 1.2,
         "max_drawdown": -0.08},
        {"window": "W2", "annualized_return": -0.05, "sharpe": -0.4,
         "max_drawdown": -0.15},
        {"window": "W3", "annualized_return": -0.02, "sharpe": -0.1,
         "max_drawdown": -0.12},
    ])
    s = oos_summary(df)
    assert abs(s["positive_window_ratio"] - 1 / 3) < 1e-4
    assert s["consistent"] is False
