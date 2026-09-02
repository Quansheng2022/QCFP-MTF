# coding: utf-8
"""Holding-period Efficiency 测试（64 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.backtest.retail_utility import holding_period_efficiency


def test_holding_efficiency():
    fast = holding_period_efficiency(0.15, 10, mfe=0.30, mae=-0.05)
    slow = holding_period_efficiency(0.18, 45, mfe=0.30, mae=-0.05)
    assert fast["return_per_capital_day"] > slow["return_per_capital_day"]
    assert fast["mfe_per_holding_day"] > slow["mfe_per_holding_day"]
    assert fast["annualized_return"] > slow["annualized_return"]


def test_holding_efficiency_zero_days():
    r = holding_period_efficiency(0.05, 0)
    assert r["holding_days"] == 1
