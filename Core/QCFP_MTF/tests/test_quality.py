# coding: utf-8
"""数据质量分级测试"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS, load_qcfp_settings
from QCFP_MTF.data.quality import assess_catalog, assess_table, worst_grade_by_stock


def _settings():
    return load_qcfp_settings()


def _good_kline(n=10):
    return pd.DataFrame({
        "stock_code": ["00700"] * n,
        "date": pd.date_range("2026-01-01", periods=n, freq="D"),
        "close": [100.0] * n,
        "volume": [1_000_000] * n,
        "amount": [1_000_000] * n,
        "turnover_rate": [0.5] * n,
        "open": [99.0] * n,
        "high": [101.0] * n,
        "low": [98.0] * n,
    })


def test_grade_a():
    res = assess_table("daily_kline", _good_kline(), _settings())
    assert res.iloc[0]["grade"] == "A"


def test_grade_d_missing():
    df = _good_kline()
    df.loc[df.index[:8], "close"] = None  # 80% 核心缺失
    res = assess_table("daily_kline", df, _settings())
    assert res.iloc[0]["grade"] == "D"


def test_grade_c_anomaly():
    df = _good_kline()
    # 真正数据错误：volume=0 但 amount>0（量额矛盾）
    df.loc[df.index[0], "volume"] = 0
    res = assess_table("daily_kline", df, _settings())
    assert res.iloc[0]["grade"] == "C"
    assert "量额矛盾" in res.iloc[0]["reasons"]


def test_fq_non_positive_price_is_clean_not_error():
    """前复权非正价格 → CLEAN（不降级），不再是数据错误。"""
    df = _good_kline()
    df.loc[df.index[0], "close"] = -1.0
    res = assess_table("daily_kline", df, _settings())
    assert res.iloc[0]["grade"] == "A"
    assert "前复权非正价格" in res.iloc[0]["reasons"]


def test_monthly_high_turnover_is_info_not_error():
    """月/季累计换手率 >=100% → 合法（INFO），不降级。"""
    df = _good_kline(3)
    df["turnover_rate"] = 122.34
    res = assess_table("monthly_kline", df, _settings())
    assert res.iloc[0]["grade"] == "A"
    assert "周期高换手" in res.iloc[0]["reasons"]


def test_empty_is_d():
    res = assess_table("weekly_kline", pd.DataFrame(), _settings())
    assert res.iloc[0]["grade"] == "D"


def test_idx_assess():
    df = pd.DataFrame({
        "date": ["2026-01-01", "2026-01-02"],
        "HSI": [20000.0, 20100.0],
        "HSCEI": [7000.0, 7050.0],
    })
    res = assess_table("idx_hist", df, _settings())
    assert res.iloc[0]["grade"] == "A"
    assert res.iloc[0]["stock_code"] == "IDX"


def test_assess_catalog_and_worst():
    catalog = {"daily_kline": _good_kline(5), "weekly_kline": _good_kline(3)}
    # 真正数据错误（量额矛盾）才触发降级；前复权负价格只算 CLEAN
    catalog["weekly_kline"].loc[0, "volume"] = 0
    assessment = assess_catalog(catalog, _settings())
    worst = worst_grade_by_stock(assessment)
    assert worst.iloc[0]["worst_grade"] == "C"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_quality 全部通过 ✅")
