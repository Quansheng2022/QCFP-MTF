# coding: utf-8
"""P 因子测试"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.structural.price_factors import build_p_factors


def _q_df():
    dates = ["2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31", "2026-03-31"]
    closes = [100.0, 110.0, 121.0, 108.9, 120.0]
    return pd.DataFrame({
        "stock_code": ["00700"] * 5,
        "stock_name": ["腾讯控股"] * 5,
        "date": pd.to_datetime(dates),
        "close": closes,
        "volume": [1_000_000] * 5,
        "amount": [100_000_000] * 5,
        "ema5": closes, "ema10": closes, "ema20": closes, "ema50": closes,
        "macd_dif": [1.0] * 5, "macd_signal": [0.5] * 5,
        "macd_histogram": [0.3] * 5,
    })


def _daily_df():
    closes = [float(x) for x in range(80, 131)]  # 80~130
    return pd.DataFrame({
        "stock_code": ["00700"] * len(closes),
        "date": pd.to_datetime(pd.date_range("2025-01-01", periods=len(closes), freq="D")),
        "close": closes,
    })


def test_p_return_and_state():
    df = build_p_factors(_q_df(), _daily_df(), DEFAULT_SETTINGS)
    assert abs(df.loc[1, "q_return"] - 10.0) < 1e-6
    assert df.loc[1, "p_state"] == "P↑"
    assert df.loc[3, "p_state"] == "P↓"  # 108.9 vs 121 = -10%
    assert pd.isna(df.loc[0, "p_state"])  # 首季无环比


def test_52w_position():
    df = build_p_factors(_q_df(), _daily_df(), DEFAULT_SETTINGS)
    pos = df.loc[1, "q_position_52w"]
    assert 0.0 <= pos <= 1.0


def test_trend_score_range():
    df = build_p_factors(_q_df(), _daily_df(), DEFAULT_SETTINGS)
    scores = df["q_trend_score"].dropna()
    assert scores.between(0, 100).all()


def test_negative_price_filtered():
    q = _q_df()
    q.loc[1, "close"] = -1.0
    df = build_p_factors(q, _daily_df(), DEFAULT_SETTINGS)
    assert pd.isna(df.loc[1, "q_return"])
    assert pd.isna(df.loc[1, "p_state"])


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_price_factors 全部通过 ✅")
