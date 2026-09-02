# coding: utf-8
"""Minimum Viable Canonical 测试（59 号：最小有效系统）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.research.minimum_viable_canonical import \
    MINIMAL_CANONICAL_STAGES, minimum_viable_canonical


def test_minimal_sufficient_when_retention_high():
    full = {"sharpe": 0.85, "mdd": -0.10, "wave_capture": 0.72,
            "practicality": 0.80}
    minimal = {"sharpe": 0.83, "mdd": -0.11, "wave_capture": 0.70,
               "practicality": 0.85}
    r = minimum_viable_canonical(full, minimal)
    assert r["overall_value_retention"] >= 0.95
    assert r["verdict"] == "MINIMAL_SUFFICIENT"
    assert "优先保留更小" in r["recommendation"]


def test_full_required_when_retention_low():
    full = {"sharpe": 0.85, "mdd": -0.10, "wave_capture": 0.72,
            "practicality": 0.80}
    minimal = {"sharpe": 0.40, "mdd": -0.25, "wave_capture": 0.35,
               "practicality": 0.80}
    r = minimum_viable_canonical(full, minimal)
    assert r["overall_value_retention"] < 0.95
    assert r["verdict"] == "FULL_REQUIRED"


def test_minimal_stages_defined():
    assert "PIT_EVIDENCE" in MINIMAL_CANONICAL_STAGES
    assert "LEDGER" in MINIMAL_CANONICAL_STAGES
    assert len(MINIMAL_CANONICAL_STAGES) == 7
