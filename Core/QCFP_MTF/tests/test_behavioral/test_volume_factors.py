# coding: utf-8
"""量因子测试"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.behavioral.volume_factors import build_volume_factors


def _m_df(volumes, turnovers):
    n = len(volumes)
    return pd.DataFrame({
        "stock_code": ["00700"] * n,
        "date": pd.date_range("2024-01-31", periods=n, freq="ME"),
        "volume": volumes,
        "turnover_rate": turnovers,
    })


def test_volume_accel_lag3():
    vols = [1_000_000.0] * 3 + [2_000_000.0, 2_000_000.0, 2_000_000.0]
    df = build_volume_factors(_m_df(vols, [2.0] * 6), DEFAULT_SETTINGS)
    assert abs(df.iloc[3]["m_volume_accel"] - 1.0) < 1e-6  # 2x / 3期前


def test_volume_direction():
    vols = [1_000_000.0] * 6 + [1_200_000.0]  # ratio ≈ 1.16 > 1.1 且 < 1.5
    df = build_volume_factors(_m_df(vols, [2.0] * 7), DEFAULT_SETTINGS)
    assert df.iloc[-1]["vol_dir"] == "↑"


def test_strong_volume_direction():
    vols = [1_000_000.0] * 6 + [3_000_000.0]  # ratio = 3 > 1.5
    df = build_volume_factors(_m_df(vols, [2.0] * 7), DEFAULT_SETTINGS)
    assert df.iloc[-1]["vol_dir"] == "↑↑"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_volume_factors 全部通过 ✅")
