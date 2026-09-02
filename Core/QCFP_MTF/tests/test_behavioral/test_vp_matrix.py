# coding: utf-8
"""量价矩阵 9 种 VP 测试"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.behavioral.vp_matrix import build_vp_regime


def _frames(chg, vol_dir, turn_dir):
    m = pd.DataFrame({
        "stock_code": ["00700"] * len(chg),
        "date": pd.date_range("2024-01-31", periods=len(chg), freq="ME"),
        "change_percent": chg,
    })
    v = pd.DataFrame({
        "stock_code": ["00700"] * len(chg),
        "month_end": m["date"].dt.strftime("%Y-%m-%d"),
        "vol_dir": vol_dir,
        "turn_dir": turn_dir,
    })
    return m, v


def test_all_regimes():
    cases = [
        (8.0, "↑", "↑", "VP_EXPANSION"),
        (8.0, "→", "→", "VP_STABLE_ASCENT"),
        (8.0, "↓", "↓", "VP_LOCKED_CANDIDATE"),
        (8.0, "↑↑", "↑↑", "VP_OVERHEAT"),
        (0.0, "↓", "↓", "VP_SHRINK"),
        (0.0, "↑", "↑", "VP_DIVERGENCE_HIGH"),
        (-8.0, "↓", "↓", "VP_DECLINE_SILENT"),
        (-8.0, "↑", "↑", "VP_SELLING_ACTIVE"),
        (-8.0, "↑↑", "↑↑", "VP_PANIC"),
        (0.0, "→", "→", "VP_NEUTRAL"),
    ]
    for chg, vd, td, expected in cases:
        m, v = _frames([chg], [vd], [td])
        out = build_vp_regime(m, v, DEFAULT_SETTINGS)
        assert out.iloc[0]["m_vp_regime"] == expected, (chg, vd, td)


def test_missing_direction():
    m, v = _frames([8.0], [None], ["↑"])
    out = build_vp_regime(m, v, DEFAULT_SETTINGS)
    assert pd.isna(out.iloc[0]["m_vp_regime"])


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_vp_matrix 全部通过 ✅")
