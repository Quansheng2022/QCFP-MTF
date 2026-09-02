# coding: utf-8
"""Chip Stability Confidence 测试"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.fusion.chip_confidence import compute_chip_confidence


def test_weighted_formula():
    score, level = compute_chip_confidence(80.0, 60.0, "C↑", DEFAULT_SETTINGS)
    assert abs(score - (0.6 * 80 + 0.4 * 60)) < 1e-6  # 72 → High
    assert level == "High"


def test_thresholds():
    assert compute_chip_confidence(60, 50, "C↑", DEFAULT_SETTINGS)[1] == "Medium"  # 56
    assert compute_chip_confidence(40, 40, "C↑", DEFAULT_SETTINGS)[1] == "Low"    # 40


def test_forced_low_on_c_down():
    score, level = compute_chip_confidence(90, 90, "C↓", DEFAULT_SETTINGS)
    assert level == "Low"  # C↓ 强制 Low，即使权重分高


def test_missing_inputs():
    assert compute_chip_confidence(None, 50, "C↑", DEFAULT_SETTINGS) == (None, None)
    assert compute_chip_confidence(50, None, "C↑", DEFAULT_SETTINGS) == (None, None)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_chip_confidence 全部通过 ✅")
