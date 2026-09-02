# coding: utf-8
"""Wave Lifecycle 测试（13 号：DISCOVERY→CONFIRMING→ACTIVE→MATURE→
EXHAUSTING→INVALID + 年龄/衰减/失效条件）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.wave.lifecycle import (WAVE_LIFECYCLE_STAGES,
                                     advance_lifecycle, start_lifecycle)


def test_stage_sequence():
    lc = start_lifecycle("01951_2024-01-01", "01951",
                         "2024-01-01", start_price=1.0,
                         invalidation_level=0.85, max_duration_days=90)
    assert lc.stage == "DISCOVERY"
    lc = advance_lifecycle(lc, "2024-01-15", 1.05, confirmed=True)
    assert lc.stage == "CONFIRMING"
    lc = advance_lifecycle(lc, "2024-01-22", 1.10, active=True)
    assert lc.stage == "ACTIVE"
    lc = advance_lifecycle(lc, "2024-02-05", 1.20, matured=True)
    assert lc.stage == "MATURE"
    assert lc.age_days >= 30
    assert lc.decay <= 1.0


def test_invalidation():
    lc = start_lifecycle("x_2024-01-01", "01951", "2024-01-01",
                         start_price=1.0, invalidation_level=0.85)
    lc = advance_lifecycle(lc, "2024-01-10", 0.80)
    assert lc.stage == "INVALID"
    assert not lc.is_alive()
    # 失效后即使 confirmed 也不能复活
    lc = advance_lifecycle(lc, "2024-01-20", 0.95, confirmed=True)
    assert lc.stage == "INVALID"


def test_max_duration_exhausting():
    lc = start_lifecycle("x_2024-01-01", "01951", "2024-01-01",
                         start_price=1.0, max_duration_days=30)
    lc = advance_lifecycle(lc, "2024-03-01", 1.0)
    assert lc.stage == "EXHAUSTING"
    assert lc.age_days > 30
    assert lc.decay < 1.0


def test_decay_curve():
    lc = start_lifecycle("x_2024-01-01", "01951", "2024-01-01",
                         start_price=1.0, max_duration_days=100)
    early = advance_lifecycle(lc, "2024-01-20", 1.0)
    assert early.decay == 1.0
    late = advance_lifecycle(lc, "2024-05-01", 1.0)
    assert late.decay < 1.0


def test_stages_constant():
    assert WAVE_LIFECYCLE_STAGES == (
        "DISCOVERY", "CONFIRMING", "ACTIVE", "MATURE",
        "EXHAUSTING", "INVALID")
