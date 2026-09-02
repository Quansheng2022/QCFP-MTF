# coding: utf-8
"""Wave Quality Decomposition 测试（73 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.wave.quality import wave_quality_decomposition


def test_early_strong_wave_beats_mature():
    early = wave_quality_decomposition(
        strength=90, persistence=80, acceleration=70, maturity=30,
        remaining_opportunity=90, confirmation=80, failure_risk=10)
    mature = wave_quality_decomposition(
        strength=95, persistence=85, acceleration=60, maturity=90,
        remaining_opportunity=35, confirmation=80, failure_risk=15)
    assert early.composite > mature.composite
    assert early.maturity < mature.maturity
    assert early.remaining_opportunity > mature.remaining_opportunity


def test_failure_risk_lowers_composite():
    low_risk = wave_quality_decomposition(strength=80, failure_risk=10)
    high_risk = wave_quality_decomposition(strength=80, failure_risk=70)
    assert low_risk.composite > high_risk.composite
