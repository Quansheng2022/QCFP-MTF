# coding: utf-8
"""周 VWAP 偏离测试"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.tactical.weekly_vwap import build_vwap_factors


def test_deviation_formula():
    df = pd.DataFrame({
        "stock_code": ["00700"],
        "date": pd.to_datetime(["2026-08-14"]),
        "close": [110.0],
        "amount": [100.0 * 1_000_000],
        "volume": [1_000_000.0],
    })
    out = build_vwap_factors(df, DEFAULT_SETTINGS)
    assert abs(out.iloc[0]["w_vwap_deviation"] - 0.10) < 1e-6


def test_zero_volume_nan():
    df = pd.DataFrame({
        "stock_code": ["00700"],
        "date": pd.to_datetime(["2026-08-14"]),
        "close": [110.0],
        "amount": [100.0 * 1_000_000],
        "volume": [0.0],
    })
    out = build_vwap_factors(df, DEFAULT_SETTINGS)
    assert pd.isna(out.iloc[0]["w_vwap_deviation"])


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_weekly_vwap 全部通过 ✅")
