# coding: utf-8
"""Trade Frequency Governor 测试（67 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.trade_frequency import trade_frequency_gate


def test_normal():
    g = trade_frequency_gate(daily_trades=2, daily_limit=5)
    assert g.allowed is True
    assert g.mode == "NORMAL"
    assert g.threshold_scale == 1.0


def test_daily_limit_tightens():
    g = trade_frequency_gate(daily_trades=6, daily_limit=5)
    assert g.mode == "TIGHTENED"
    assert g.threshold_scale > 1.0


def test_signal_noise_watch():
    g = trade_frequency_gate(daily_trades=2, daily_limit=5,
                             signal_frequency_trend=1.5, edge_trend=0.5)
    assert g.mode == "WATCH"
    assert g.allowed is False


def test_turnover_budget_hold():
    g = trade_frequency_gate(daily_trades=2, daily_limit=5,
                             portfolio_turnover=3.5,
                             portfolio_turnover_budget=3.0)
    assert g.mode == "HOLD"
    assert g.allowed is False
