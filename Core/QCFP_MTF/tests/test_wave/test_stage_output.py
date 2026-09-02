# coding: utf-8
"""Wave Multi-stage Output 测试（14 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.wave.stage_output import WAVE_STAGES, wave_stage_output


def test_stage_classification():
    assert wave_stage_output(score=0.7)["wave_stage"] == "TRIGGER"
    assert wave_stage_output(score=0.7, velocity=0.05)[
        "wave_stage"] == "EXPANSION"
    assert wave_stage_output(score=0.7, velocity=0.05,
                             acceleration=0.08)["wave_stage"] \
        == "ACCELERATION"
    assert wave_stage_output(score=0.7, exhaustion=0.9)[
        "wave_stage"] == "DECAY"
    assert wave_stage_output(breakdown=True)["wave_stage"] == "DECAY"


def test_stage_output_fields():
    o = wave_stage_output(score=0.78, strength=0.8, age=5,
                          velocity=0.02, acceleration=0.01)
    assert o["wave_score"] == 0.78
    assert o["wave_strength"] == 0.8
    assert o["wave_age"] == 5
    assert all(k in o for k in ("wave_velocity", "wave_acceleration",
                                "wave_exhaustion", "wave_breakdown"))


def test_stages_constant():
    assert WAVE_STAGES == ("FORMATION", "TRIGGER", "EXPANSION",
                           "ACCELERATION", "DISTRIBUTION", "DECAY")
