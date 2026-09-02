# coding: utf-8
"""F 因子测试"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.structural.flow_factors import build_f_factors


def _chip_df():
    quarters = [f"2024/Q{q}" for q in range(1, 5)] + [f"2025/Q{q}" for q in range(1, 5)]
    end_dates = ["2024-03-31", "2024-06-30", "2024-09-30", "2024-12-31",
                 "2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31"]
    rows = []
    for i, q in enumerate(quarters):
        rows.append({
            "stock_code": "00700", "stock_name": "腾讯控股", "quarter": q,
            "quarter_end_date": end_dates[i],
            "institutional_flow": float(i + 1),  # 单调递增
        })
    for q in ["2026/Q1", "2026/Q2"]:
        rows.append({
            "stock_code": "03033", "stock_name": "ETF", "quarter": q,
            "quarter_end_date": "2026-03-31" if q == "2026/Q1" else "2026-06-30",
            "institutional_flow": None,  # 无机构资金流
        })
    return pd.DataFrame(rows)


def test_flow_z_up():
    df = build_f_factors(_chip_df(), DEFAULT_SETTINGS)
    last = df[df["stock_code"] == "00700"].iloc[-1]
    assert last["q_inst_flow_z"] > 0.5
    assert last["f_state"] == "F↑"


def test_flow_unknown_when_missing():
    df = build_f_factors(_chip_df(), DEFAULT_SETTINGS)
    etf = df[df["stock_code"] == "03033"]
    assert (etf["f_state"] == "F_UNKNOWN").all()


def test_ifa_zscore_cross_sectional():
    df = build_f_factors(_chip_df(), DEFAULT_SETTINGS)
    q2 = df[df["quarter"] == "2025/Q2"]
    if len(q2) >= 2:
        assert q2["q_ifa_zscore"].notna().any()


def test_quarter_and_period_end():
    df = build_f_factors(_chip_df(), DEFAULT_SETTINGS)
    row = df[df["quarter"] == "2025/Q2"].iloc[0]
    assert row["period_end"] == "2025-06-30"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_flow_factors 全部通过 ✅")
