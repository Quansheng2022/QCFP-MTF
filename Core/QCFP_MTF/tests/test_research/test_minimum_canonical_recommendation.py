# coding: utf-8
"""Minimum Viable Canonical 推荐测试（新 59 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.research.minimum_viable_canonical import \
    minimum_canonical_recommendation


def test_simplify_when_high_retention_low_complexity():
    full = {"sharpe": 1.31, "mdd": -0.10, "wave_capture": 0.72,
            "practicality": 0.80}
    minimal = {"sharpe": 1.29, "mdd": -0.11, "wave_capture": 0.70,
               "practicality": 0.85}
    r = minimum_canonical_recommendation(full, minimal,
                                         full_complexity=1.0,
                                         minimal_complexity=0.5)
    assert r["verdict"] == "SIMPLIFY"
    assert r["complexity_ratio"] == 0.5
    assert r["minimal_canonical_core"]


def test_full_required_when_value_lost():
    full = {"sharpe": 0.85, "mdd": -0.10, "wave_capture": 0.72,
            "practicality": 0.80}
    minimal = {"sharpe": 0.40, "mdd": -0.25, "wave_capture": 0.35,
               "practicality": 0.80}
    r = minimum_canonical_recommendation(full, minimal)
    assert r["verdict"] == "FULL_REQUIRED"
