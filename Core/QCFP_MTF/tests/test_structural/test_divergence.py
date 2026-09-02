# coding: utf-8
"""三维背离测试"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.structural.divergence import compute_divergence


def test_top_and_bottom_divergence():
    c_z = pd.Series([2.0, -2.0, 0.5], index=[0, 1, 2])
    p_z = pd.Series([-2.0, 2.0, 0.5], index=[0, 1, 2])
    f_z = pd.Series([1.0, 1.0, 0.0], index=[0, 1, 2])
    df = compute_divergence(c_z, f_z, p_z, threshold=1.0)
    assert df.loc[0, "cpd"] == "筹码顶背离"
    assert df.loc[1, "cpd"] == "筹码底背离"
    assert df.loc[2, "cpd"] == ""
    assert df["cpd_flag"].tolist() == [1, 1, 0]


def test_nan_handling():
    c_z = pd.Series([2.0, np.nan], index=[0, 1])
    p_z = pd.Series([-2.0, -2.0], index=[0, 1])
    f_z = pd.Series([np.nan, np.nan], index=[0, 1])
    df = compute_divergence(c_z, f_z, p_z, threshold=1.0)
    assert df.loc[0, "cpd"] == "筹码顶背离"
    assert df.loc[1, "cpd"] == ""
    assert df.loc[0, "fpd"] == ""
    assert df.loc[1, "cfd"] == ""


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_divergence 全部通过 ✅")
