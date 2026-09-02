# coding: utf-8
"""换手因子 T1~T5 测试"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.behavioral.turnover_factors import build_turnover_factors


def _m_df(turnover):
    n = len(turnover)
    return pd.DataFrame({
        "stock_code": ["00700"] * n,
        "stock_name": ["腾讯控股"] * n,
        "date": pd.date_range("2024-01-31", periods=n, freq="ME"),
        "turnover_rate": turnover,
    })


def test_extreme_turnover_t5():
    # 单调飙升的换手 → 最后一个 T5
    series = [float(1 + i * 0.9) for i in range(18)]
    df = build_turnover_factors(_m_df(series), DEFAULT_SETTINGS)
    assert df.iloc[-1]["turnover_liquidity_regime"] == "T5"
    assert df.iloc[-1]["m_turnover_zscore"] > 1.5


def test_low_turnover_t1():
    series = [5.0] * 18 + [0.01, 0.01, 0.01]
    df = build_turnover_factors(_m_df(series), DEFAULT_SETTINGS)
    assert df.iloc[-1]["turnover_liquidity_regime"] == "T1"


def test_zero_turnover_nan():
    series = [2.0] * 12 + [0.0]
    df = build_turnover_factors(_m_df(series), DEFAULT_SETTINGS)
    assert pd.isna(df.iloc[-1]["m_turnover_zscore"])


def test_ma_ratio():
    series = [2.0] * 6 + [4.0]
    df = build_turnover_factors(_m_df(series), DEFAULT_SETTINGS)
    # MA6 含当期：[2,2,2,2,2,4] 均值 2.333 → ratio ≈ 1.714
    assert abs(df.iloc[-1]["m_turnover_ma_ratio"] - 1.7143) < 0.01


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_turnover_factors 全部通过 ✅")
