# coding: utf-8
"""数据加载器测试（依赖真实数据库）"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.data.loader import (get_available_stocks, load_idx_hist,
                                  load_institutional_holdings, load_kline,
                                  load_moneyflow, load_stock_list,
                                  parse_quarter_period, quarter_end_date)

try:  # 依赖真实数据库 → integration 标记
    import pytest
    pytestmark = pytest.mark.integration
except ImportError:
    pass


def test_stock_list():
    df = load_stock_list()
    assert not df.empty
    assert "stock_code" in df.columns
    assert df["stock_code"].str.match(r"^\d{5}$").all()


def test_load_kline_daily():
    df = load_kline("daily")
    assert not df.empty
    assert {"stock_code", "date", "close", "volume", "turnover_rate"} <= set(df.columns)
    assert pd.api.types.is_datetime64_any_dtype(df["date"])
    assert df["stock_code"].str.match(r"^\d{5}$").all()


def test_load_kline_quarterly():
    df = load_kline("quarterly")
    assert not df.empty


def test_load_moneyflow():
    df = load_moneyflow("daily")
    assert not df.empty
    assert {"capital_trend", "extra_large", "large", "medium", "small"} <= set(df.columns)


def test_load_idx():
    df = load_idx_hist()
    assert not df.empty
    assert "HSI" in df.columns


def test_institutional_holdings():
    df = load_institutional_holdings()
    assert not df.empty
    assert "quarter_end_date" in df.columns
    assert "2026/Q2" in set(df["period_text"])
    row = df[df["period_text"] == "2026/Q2"].iloc[0]
    assert str(row["quarter_end_date"])[:10] == "2026-06-30"


def test_parse_quarter():
    assert parse_quarter_period("2026/Q2") == (2026, 2)
    assert parse_quarter_period("2025Q4") == (2025, 4)
    assert quarter_end_date("2026/Q2") == "2026-06-30"
    assert parse_quarter_period("bad") is None


def test_available_stocks():
    df = get_available_stocks("daily")
    assert len(df) >= 10


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_loader 全部通过 ✅")
