# coding: utf-8
"""Alpha Half-Life 测试（46 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.alpha.halflife import alpha_half_life, alpha_weight


def test_half_life_computation():
    # IC 0.12 → 0.04 经过 36 个月：ratio=1/3, half_life = 36×ln(0.5)/ln(1/3)≈22.7
    r = alpha_half_life(0.12, 0.04, 36)
    assert r["half_life_months"] is not None
    assert r["half_life_months"] > 0
    assert r["weight_scale"] < 1.0


def test_alpha_weight_decay():
    r = alpha_weight(0.12, 0.04, 36, base_weight=0.20)
    assert r["adjusted_weight"] < r["base_weight"]


def test_no_decay_full_weight():
    r = alpha_half_life(0.12, 0.14, 12)     # IC 未衰减
    assert r["half_life_months"] is None
    assert r["weight_scale"] == 1.0
