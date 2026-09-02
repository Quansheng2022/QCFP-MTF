# coding: utf-8
"""回测信号时间线（available_date 对齐）测试"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.backtest.data_pipeline import build_signal_timeline
from QCFP_MTF.config.settings import DEFAULT_SETTINGS


def _frames():
    structural = pd.DataFrame({
        "stock_code": ["00700", "00700"],
        "period_end": ["2026-03-31", "2026-06-30"],
        "available_date": ["2026-05-15", "2026-08-14"],
        "structural_regime": ["STRUCTURAL_DECLINE", "STRUCTURAL_BULLISH"],
        "c_state": ["C↓", "C↑"],
        "f_state": ["F↓", "F↑"],
        "p_state": ["P↓", "P↑"],
        "q_trend_score": [30.0, 70.0],
        "q_position_52w": [0.10, 0.55],
        "data_quality": ["A", "A"],
    })
    monthly = pd.DataFrame({
        "stock_code": ["00700", "00700", "00700"],
        "month_end": ["2026-04-30", "2026-05-31", "2026-07-31"],
        "monthly_behavior_state": ["Stable", "Improving", "Deteriorating"],
        "cbi_score": [50.0, 60.0, 40.0],
        "cbi_state": ["CBI_STABLE", "CBI_STABLE", "CBI_TURBULENT"],
        "cost_position": ["COST_NEUTRAL", "COST_ADVANTAGE", "COST_DISADVANTAGE"],
        "data_quality": ["A", "A", "A"],
    })
    weekly = pd.DataFrame({
        "stock_code": ["00700"] * 4,
        "stock_name": ["腾讯控股"] * 4,
        "week_end": ["2026-05-01", "2026-05-29", "2026-08-14", "2026-08-21"],
        "tactical_signal": ["Consolidation", "Breakout", "Breakdown", "Consolidation"],
        "data_quality": ["A", "A", "A", "A"],
    })
    chip = pd.DataFrame({
        "stock_code": ["00700", "00700"],
        "quarter_end_date": ["2026-03-31", "2026-06-30"],
        "chip_structure_score": [50.0, 80.0],
    })
    idx = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=200, freq="D"),
        "HSI": [20000.0 + i for i in range(200)],
        "VHSI": [20.0] * 200,
    })
    return structural, monthly, weekly, chip, idx


def test_available_date_alignment():
    structural, monthly, weekly, chip, idx = _frames()
    out = build_signal_timeline(structural, monthly, weekly, chip, idx,
                                DEFAULT_SETTINGS)
    # 2026-05-01：无可用结构数据 → DATA_INSUFFICIENT
    r1 = out[out["decision_date"] == "2026-05-01"].iloc[0]
    assert r1["mtf_regime"] == "DATA_INSUFFICIENT"
    # 2026-05-29：用 available 2026-05-15 的季度（DECLINE）
    r2 = out[out["decision_date"] == "2026-05-29"].iloc[0]
    assert r2["structural_available_date"] == "2026-05-15"
    assert r2["structural_regime"] == "STRUCTURAL_DECLINE"
    # 2026-08-14：用 available 2026-08-14 的季度（BULLISH）
    r3 = out[out["decision_date"] == "2026-08-14"].iloc[0]
    assert r3["structural_available_date"] == "2026-08-14"
    assert r3["structural_regime"] == "STRUCTURAL_BULLISH"


def test_timeline_columns():
    structural, monthly, weekly, chip, idx = _frames()
    out = build_signal_timeline(structural, monthly, weekly, chip, idx,
                                DEFAULT_SETTINGS)
    assert {"mtf_regime", "action_signal", "risk_level", "market_context"} \
        <= set(out.columns)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_data_pipeline 全部通过 ✅")
