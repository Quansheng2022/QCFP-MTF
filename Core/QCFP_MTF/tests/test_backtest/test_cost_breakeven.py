# coding: utf-8
"""Cost Break-even Analysis 测试（25 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.backtest.cost_model import cost_breakeven_analysis


def test_breakeven_detects_failure():
    results = [
        {"factor": 1.0, "annualized_return": 0.12, "sharpe": 1.2,
         "max_drawdown": -0.15},
        {"factor": 1.5, "annualized_return": 0.06, "sharpe": 0.7,
         "max_drawdown": -0.16},
        {"factor": 2.0, "annualized_return": 0.01, "sharpe": 0.2,
         "max_drawdown": -0.18},
        {"factor": 3.0, "annualized_return": -0.05, "sharpe": -0.3,
         "max_drawdown": -0.22},
    ]
    r = cost_breakeven_analysis(results)
    assert r["break_even_factor"] == 2.0
    assert r["rows"][0]["band"] == "Robust"
    assert r["rows"][-1]["band"] == "Broken"


def test_breakeven_robust():
    results = [
        {"factor": 1.0, "annualized_return": 0.10, "sharpe": 1.0,
         "max_drawdown": -0.10},
        {"factor": 2.0, "annualized_return": 0.07, "sharpe": 0.8,
         "max_drawdown": -0.12},
        {"factor": 3.0, "annualized_return": 0.05, "sharpe": 0.6,
         "max_drawdown": -0.13},
    ]
    r = cost_breakeven_analysis(results)
    assert r["verdict"] == "ROBUST_TO_COST"
