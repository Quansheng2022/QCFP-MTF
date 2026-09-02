# coding: utf-8
"""标准化工具测试"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.common.normalization import (pctl_rank, scale_0_100, standardize_0_100,
                                           winsorize, zscore)


def test_winsorize():
    s = pd.Series([1, 2, 3, 4, 100])
    out = winsorize(s, lower=0.1, upper=0.9)
    # 极端值 100 必须被截尾到 90% 分位数
    assert out.max() < 100.0
    assert abs(out.iloc[-1] - 61.6) < 1e-9  # [1,2,3,4,100] 的 90% 分位（线性插值）
    assert out.min() >= 1.0


def test_zscore():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    z = zscore(s)
    assert abs(z.mean()) < 1e-9
    assert abs(z.std(ddof=0) - 1.0) < 1e-9


def test_scale_0_100():
    s = pd.Series([1.0, 2.0, 3.0])
    out = scale_0_100(s)
    assert out.min() == 0.0 and out.max() == 100.0


def test_standardize_pipeline():
    rng = np.random.default_rng(42)
    s = pd.Series(rng.normal(0, 1, 500))
    out = standardize_0_100(s)
    assert out.min() >= 0 and out.max() <= 100


def test_constant_series():
    s = pd.Series([5.0, 5.0, 5.0])
    assert zscore(s).abs().max() == 0
    assert scale_0_100(s).iloc[0] == 50.0


def test_pctl_rank():
    s = pd.Series([1.0, 2.0, 3.0, 4.0])
    out = pctl_rank(s)
    assert out.min() == 0.25 and out.max() == 1.0


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_normalization 全部通过 ✅")
