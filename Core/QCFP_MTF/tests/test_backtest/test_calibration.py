# coding: utf-8
"""校准网格测试（合成小数据）"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.backtest.calibration import run_grid
from QCFP_MTF.config.settings import DEFAULT_SETTINGS


def test_run_grid_small():
    structural = pd.DataFrame({
        "stock_code": ["00700"] * 4,
        "period_end": ["2025-12-31", "2026-03-31", "2026-06-30", "2026-09-30"],
        "available_date": ["2026-02-14", "2026-05-15", "2026-08-14", "2026-11-14"],
        "structural_regime": ["STRUCTURAL_BULLISH"] * 4,
        "c_state": ["C↑"] * 4,
        "f_state": ["F↑"] * 4,
        "p_state": ["P↑"] * 4,
        "q_trend_score": [70.0] * 4,
        "q_position_52w": [0.40] * 4,
        "data_quality": ["A"] * 4,
    })
    monthly = pd.DataFrame({
        "stock_code": ["00700"] * 3,
        "month_end": ["2026-01-31", "2026-05-31", "2026-08-31"],
        "monthly_behavior_state": ["Improving"] * 3,
        "cbi_score": [60.0, 65.0, 70.0],
        "cbi_state": ["CBI_STABLE"] * 3,
        "cost_position": ["COST_NEUTRAL"] * 3,
        "data_quality": ["A"] * 3,
    })
    weekly = pd.DataFrame({
        "stock_code": ["00700"] * 4,
        "stock_name": ["腾讯控股"] * 4,
        "week_end": ["2026-06-05", "2026-06-12", "2026-06-19", "2026-06-26"],
        "tactical_signal": ["Breakout"] * 4,
        "data_quality": ["A"] * 4,
    })
    chip = pd.DataFrame({
        "stock_code": ["00700"] * 2,
        "quarter_end_date": ["2026-03-31", "2026-06-30"],
        "chip_structure_score": [70.0, 75.0],
    })
    idx = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=180, freq="D"),
        "HSI": [20000.0 + i for i in range(180)],
        "VHSI": [20.0] * 180,
    })
    weekly_kl = pd.DataFrame({
        "stock_code": ["00700"] * 4,
        "date": pd.to_datetime(["2026-06-05", "2026-06-12", "2026-06-19", "2026-06-26"]),
        "close": [100.0, 105.0, 110.0, 115.0],
    })
    grid = [
        {"fusion": {"chip_confidence": {"quarterly_chip_weight": 0.5}},
         "backtest": {"position_target": {"REDUCE": 0.3}}},
        {"fusion": {"chip_confidence": {"quarterly_chip_weight": 0.7}},
         "backtest": {"position_target": {"REDUCE": 0.7}}},
    ]
    out = run_grid(structural, monthly, weekly, chip, idx, weekly_kl,
                   DEFAULT_SETTINGS, grid)
    assert len(out) == 2
    assert "sharpe" in out.columns


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_calibration 全部通过 ✅")
