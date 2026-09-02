# coding: utf-8
"""月线阶段判定测试"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.behavioral.monthly_stage import build_monthly_stage


def test_improving():
    vp = pd.Series(["VP_EXPANSION"], index=[0])
    t = pd.Series(["T3"], index=[0])
    assert build_monthly_stage(vp, t).iloc[0] == "Improving"


def test_improving_blocked_by_extreme_t():
    vp = pd.Series(["VP_EXPANSION"], index=[0])
    t = pd.Series(["T5"], index=[0])
    assert build_monthly_stage(vp, t).iloc[0] != "Improving"


def test_stable():
    vp = pd.Series(["VP_SHRINK"], index=[0])
    t = pd.Series(["T2"], index=[0])
    assert build_monthly_stage(vp, t).iloc[0] == "Stable"


def test_deteriorating():
    for vp in ["VP_OVERHEAT", "VP_PANIC", "VP_DECLINE_SILENT"]:
        s = pd.Series([vp], index=[0])
        t = pd.Series(["T4"], index=[0])
        assert build_monthly_stage(s, t).iloc[0] == "Deteriorating"


def test_missing():
    vp = pd.Series([None], index=[0])
    t = pd.Series(["T3"], index=[0])
    assert pd.isna(build_monthly_stage(vp, t).iloc[0])


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_monthly_stage 全部通过 ✅")
