# coding: utf-8
"""E2E 一致性测试（P0-4）

同一输入从 State → Action → Target → Backtest → Report 必须一致：
    Report MTF State == DSS MTF State
    Report Action    == DSS Action
    Report Target    == Backtest Target
    Report Stop      == Backtest Stop
"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.backtest.data_pipeline import build_signal_timeline
from QCFP_MTF.backtest.engine import run_backtest
from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.decision.stop_loss import stop_loss_buffer_pct
from QCFP_MTF.scripts.dss_report import (display_action, position_advice,
                                         strategic_position, trade_intent,
                                         trade_interpretation)


def _frames():
    structural = pd.DataFrame({
        "stock_code": ["00700"],
        "period_end": ["2026-03-31"],
        "available_date": ["2026-05-15"],
        "structural_regime": ["STRUCTURAL_DECLINE"],
        "c_state": ["C→"], "f_state": ["F→"], "p_state": ["P→"],
        "q_trend_score": [40.0], "q_position_52w": [0.03],
        "data_quality": ["A"],
    })
    monthly = pd.DataFrame({
        "stock_code": ["00700"],
        "month_end": ["2026-04-30"],
        "monthly_behavior_state": ["Improving"],
        "cbi_score": [55.0], "cbi_state": ["CBI_STABLE"],
        "cost_position": ["COST_NEUTRAL"], "data_quality": ["A"],
    })
    weekly = pd.DataFrame({
        "stock_code": ["00700", "00700"], "stock_name": ["腾讯控股", "腾讯控股"],
        "week_end": ["2026-05-29", "2026-06-05"],
        "tactical_signal": ["Consolidation", "Consolidation"],
        "data_quality": ["A", "A"],
    })
    chip = pd.DataFrame({
        "stock_code": ["00700"], "quarter_end_date": ["2026-03-31"],
        "chip_structure_score": [60.0],
    })
    idx = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=200, freq="D"),
        "HSI": [20000.0 + i for i in range(200)],
        "VHSI": [20.0] * 200,
    })
    weekly_kl = pd.DataFrame({
        "stock_code": ["00700", "00700", "00700"],
        "date": pd.to_datetime(["2026-05-22", "2026-05-29", "2026-06-05"]),
        "high": [10.0, 10.6, 11.0], "low": [9.8, 10.2, 10.7],
        "close": [10.0, 10.5, 10.9],
    })
    return structural, monthly, weekly, chip, idx, weekly_kl


def test_e2e_state_action_target_stop_consistent():
    structural, monthly, weekly, chip, idx, weekly_kl = _frames()
    sig = build_signal_timeline(structural, monthly, weekly, chip, idx,
                                DEFAULT_SETTINGS)
    row = sig.iloc[0]
    # State：战术覆盖触发 BULLISH_WARNING
    assert row["mtf_regime"] == "BULLISH_WARNING"
    assert row["is_override"]
    # Action（P0-C 新 7 号）：报告解释事实，不制造事实——
    # CanonicalAction 原样展示 REDUCE，解释层单独说明试多语义。
    assert row["action_signal"] == "REDUCE"
    assert trade_intent(row) == "REDUCE"
    assert display_action(row) == "REDUCE"
    assert "Tactical test condition" in trade_interpretation(row)
    assert strategic_position(row) == "BEARISH"
    # Target：CQS=1 → 20%
    assert abs(float(row["target"]) - 0.2) < 1e-9
    assert position_advice(row, DEFAULT_SETTINGS).startswith("20%")
    # Backtest：仓位次周生效 = target.shift(1)
    bt = run_backtest(sig, weekly_kl, DEFAULT_SETTINGS)
    assert bt.iloc[0]["position"] == 0.0
    assert abs(float(bt.iloc[1]["position"]) - 0.2) < 1e-9
    # Stop：报告展示与回测缓冲同源
    assert abs(stop_loss_buffer_pct(DEFAULT_SETTINGS) - 0.02) < 1e-9


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_e2e_consistency 全部通过 ✅")
