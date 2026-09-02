# coding: utf-8
"""周换手检测测试"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.tactical.weekly_turnover import build_turnover_factors


def _w_df(turnovers):
    n = len(turnovers)
    return pd.DataFrame({
        "stock_code": ["00700"] * n,
        "date": pd.date_range("2026-01-02", periods=n, freq="W-FRI"),
        "turnover_rate": turnovers,
    })


def test_deviation_vs_quarter_avg():
    turns = [2.0] * 14 + [4.0]  # 4 vs MA13≈2 → deviation≈1
    df = build_turnover_factors(_w_df(turns), DEFAULT_SETTINGS)
    # MA13 含当期：[2×12, 4] 均值 2.154 → deviation = 4/2.154 - 1 ≈ 0.857
    assert abs(df.iloc[-1]["w_turnover_deviation"] - 0.8571) < 0.01


def test_spike_flag():
    turns = [1.0] * 10 + [3.0]  # 3 > MA8(1.0)*2
    df = build_turnover_factors(_w_df(turns), DEFAULT_SETTINGS)
    assert df.iloc[-1]["w_turnover_spike"] == 1


def test_no_spike():
    turns = [1.0] * 10 + [1.5]  # 1.5 < 2.0
    df = build_turnover_factors(_w_df(turns), DEFAULT_SETTINGS)
    assert df.iloc[-1]["w_turnover_spike"] == 0


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_weekly_turnover 全部通过 ✅")
