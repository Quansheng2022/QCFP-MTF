# coding: utf-8
"""周量检测测试"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.tactical.weekly_volume import build_volume_factors


def _w_df(volumes):
    n = len(volumes)
    return pd.DataFrame({
        "stock_code": ["00700"] * n,
        "date": pd.date_range("2026-01-02", periods=n, freq="W-FRI"),
        "volume": volumes,
    })


def test_breakout_flag():
    vols = [1_000_000.0] * 22 + [3_000_000.0]  # ratio ≈ 3 > 1.8
    df = build_volume_factors(_w_df(vols), DEFAULT_SETTINGS)
    assert df.iloc[-1]["w_volume_breakout"] == 1
    assert df.iloc[-1]["w_volume_shrink"] == 0


def test_shrink_flag():
    vols = [1_000_000.0] * 22 + [100_000.0]  # ratio ≈ 0.1 < 0.5
    df = build_volume_factors(_w_df(vols), DEFAULT_SETTINGS)
    assert df.iloc[-1]["w_volume_shrink"] == 1
    assert df.iloc[-1]["w_volume_breakout"] == 0


def test_window_insufficient_zero():
    vols = [1_000_000.0] * 5
    df = build_volume_factors(_w_df(vols), DEFAULT_SETTINGS)
    assert df.iloc[-1]["w_volume_breakout"] == 0


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_weekly_volume 全部通过 ✅")
