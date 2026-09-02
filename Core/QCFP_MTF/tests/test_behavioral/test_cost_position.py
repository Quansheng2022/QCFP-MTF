# coding: utf-8
"""Cost Position 测试"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.behavioral.cost_position import build_cost_position


def _frames(close):
    m = pd.DataFrame({
        "stock_code": ["00700"],
        "stock_name": ["腾讯控股"],
        "date": pd.to_datetime(["2026-07-31"]),
        "close": [close],
        "amount": [100.0 * 1_000_000],
        "volume": [1_000_000.0],
    })
    w = pd.DataFrame({
        "stock_code": ["00700"],
        "date": pd.to_datetime(["2026-07-31"]),
        "amount": [100.0 * 1_000_000],
        "volume": [1_000_000.0],
    })
    q = pd.DataFrame({
        "stock_code": ["00700"],
        "date": pd.to_datetime(["2026-06-30"]),
        "amount": [90.0 * 1_000_000],
        "volume": [1_000_000.0],
    })
    return m, w, q


def test_advantage():
    m, w, q = _frames(close=110.0)  # > 月 VWAP 100 与 季 VWAP 90
    df = build_cost_position(m, w, q, DEFAULT_SETTINGS)
    assert df.iloc[0]["cost_position"] == "COST_ADVANTAGE"
    assert abs(df.iloc[0]["cost_vs_monthly_vwap"] - 0.10) < 1e-6


def test_disadvantage():
    m, w, q = _frames(close=85.0)
    df = build_cost_position(m, w, q, DEFAULT_SETTINGS)
    assert df.iloc[0]["cost_position"] == "COST_DISADVANTAGE"


def test_neutral():
    m, w, q = _frames(close=101.0)  # 月 VWAP 100 附近
    df = build_cost_position(m, w, q, DEFAULT_SETTINGS)
    assert df.iloc[0]["cost_position"] == "COST_NEUTRAL"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_cost_position 全部通过 ✅")
