# coding: utf-8
"""MFE/MAE Benchmark 测试（63 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.monitoring.benchmark import benchmark_deviation, \
    mfe_mae_benchmark


def _trades():
    return [
        {"wave_type": "BREAKOUT", "entry_type": "PULLBACK",
         "market_regime": "Bull", "mfe": 0.18, "mae": -0.05,
         "holding_days": 15, "net_return": 0.12},
        {"wave_type": "BREAKOUT", "entry_type": "PULLBACK",
         "market_regime": "Bull", "mfe": 0.16, "mae": -0.04,
         "holding_days": 14, "net_return": 0.10},
        {"wave_type": "BREAKOUT", "entry_type": "PULLBACK",
         "market_regime": "Bull", "mfe": 0.20, "mae": -0.06,
         "holding_days": 16, "net_return": 0.15},
        {"wave_type": "RECOVERY", "entry_type": "BREAKOUT",
         "market_regime": "Bear", "mfe": 0.09, "mae": -0.04,
         "holding_days": 8, "net_return": 0.04},
    ]


def test_mfe_mae_benchmark():
    b = mfe_mae_benchmark(_trades())
    key = "BREAKOUT|PULLBACK|Bull"
    assert key in b
    assert b[key]["n"] == 3
    assert b[key]["mfe_median"] == 0.18
    assert b[key]["mae_median"] == -0.05
    assert b[key]["best_holding_period"] is not None


def test_benchmark_deviation():
    b = mfe_mae_benchmark(_trades())
    trade = {"wave_type": "BREAKOUT", "entry_type": "PULLBACK",
             "market_regime": "Bull", "mfe": 0.08, "mae": -0.10}
    dev = benchmark_deviation(trade, b)
    assert dev["n"] == 3
    assert dev["outlier"] is True
    assert dev["deviation"]["mfe_deviation"] < 0
