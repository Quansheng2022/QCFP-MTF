# coding: utf-8
"""WaveOpportunity 2.8 强化字段测试（12 号：波段画像完整化）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.wave.label import WaveLabel
from QCFP_MTF.wave.opportunity import (WaveOpportunity,
                                       build_wave_opportunity)
from QCFP_MTF.wave.signal import WaveSignal


def test_opportunity_enhanced_fields():
    label = WaveLabel("01951", "2024-01-05", "2024-06-28",
                      "2024-09-30", gain=0.616)
    signal = WaveSignal("UP", 0.8, 6, 0.05, True, False)
    op = build_wave_opportunity(
        label, duration=26, wave_signal=signal,
        expected_duration=18, expected_mfe=0.25, expected_mae=0.08,
        invalidation=8.5, entry_zone_low=9.0, entry_zone_high=9.5,
        confirmation="VOLUME")
    assert op.wave_type == ""
    assert op.strength == 0.8
    assert op.direction == "UP"
    assert op.expected_duration == 18
    assert op.expected_mfe == 0.25
    assert op.expected_mae == 0.08
    assert op.invalidation == 8.5
    assert op.entry_zone_low == 9.0
    assert op.entry_zone_high == 9.5
    assert op.confirmation == "VOLUME"
    assert op.as_dict()["wave_id"] == "01951_2024-01-05"


def test_default_expiry():
    label = WaveLabel("01951", "2024-01-05", "2024-06-28",
                      "2024-09-30", gain=0.5)
    op = build_wave_opportunity(label)
    assert op.expiry == ""
    class _Snap:
        decision_date = "2024-02-01"
        institutional_state = "ACCUMULATION"
        institutional_permission = "ALLOW"
    op2 = build_wave_opportunity(
        label, snap_at_trigger=_Snap())
    assert op2.expiry == "2024-03-02"
