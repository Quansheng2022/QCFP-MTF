# coding: utf-8
"""C 因子测试"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.structural.chip_factors import build_c_factors


def _ih_df():
    return pd.DataFrame({
        "stock_code": ["00700"] * 4,
        "stock_name": ["腾讯控股"] * 4,
        "quarter": ["2025/Q4", "2026/Q1", "2026/Q2", "2026/Q3"],
        "quarter_end_date": ["2025-12-31", "2026-03-31", "2026-06-30", "2026-09-30"],
        "source_period": ["2025/Q4", "2026/Q1", "2026/Q2", "2026/Q3"],
        "holder_pct_qoq_pp": [1.0, -1.0, 0.2, 1.0],
        "holder_quantity_qoq_pct": [2.0, -2.0, 0.5, 3.0],
        "institution_quantity_qoq_pct": [1.5, -1.5, 0.3, 2.0],
        "corporate_action_flag": [0, 0, 0, 1],
    })


def test_direction_states():
    df = build_c_factors(_ih_df(), DEFAULT_SETTINGS)
    states = list(df["c_state"])
    assert states[:3] == ["C↑", "C↓", "C→"]
    assert pd.isna(states[3])


def test_corporate_action_masked():
    df = build_c_factors(_ih_df(), DEFAULT_SETTINGS)
    assert pd.isna(df.loc[3, "c_state"])
    assert "屏蔽" in df.loc[3, "c_reason"]


def test_confidence():
    df = build_c_factors(_ih_df(), DEFAULT_SETTINGS)
    assert df["c_confidence"].tolist() == [2, 2, 2, 2]


def test_period_end_format():
    df = build_c_factors(_ih_df(), DEFAULT_SETTINGS)
    assert df["period_end"].tolist() == ["2025-12-31", "2026-03-31",
                                         "2026-06-30", "2026-09-30"]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_chip_factors 全部通过 ✅")
