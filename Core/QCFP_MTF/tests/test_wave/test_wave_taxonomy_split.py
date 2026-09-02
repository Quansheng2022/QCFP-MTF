# coding: utf-8
"""Wave Taxonomy 唯一性测试（Convergence 新 9B 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.wave.canonical import DIAGNOSTIC_WAVE_PHASES, \
    PRODUCTION_WAVE_TAXONOMY, production_wave_taxonomy_check, \
    wave_taxonomy_split


def test_production_lifecycle_only():
    assert len(PRODUCTION_WAVE_TAXONOMY) == 6
    assert wave_taxonomy_split("CONFIRMING")["production_governance"] is True


def test_diagnostic_phase_research_only():
    r = wave_taxonomy_split("EXPANSION")
    assert r["kind"] == "wave_phase_diagnostic"
    assert r["production_governance"] is False
    assert r["verdict"] == "RESEARCH_ONLY_DIAGNOSTIC"


def test_duplicate_taxonomy_detected():
    r = production_wave_taxonomy_check(
        {"engine": "CONFIRMING", "diag_module": "ACCELERATION"})
    assert r["verdict"] == "DUPLICATE_TAXONOMY"
    assert r["violations"][0]["stage"] == "ACCELERATION"
    assert DIAGNOSTIC_WAVE_PHASES
