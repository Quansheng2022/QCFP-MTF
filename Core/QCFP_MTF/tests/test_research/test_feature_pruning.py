# coding: utf-8
"""Feature Pruning 测试（33 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.research.feature_pruning import feature_pruning


def _features():
    return {
        "wave_quality": {"predictive_contribution": 0.4,
                         "incremental_alpha": 0.3, "stability": 0.5,
                         "correlation": 0.2, "data_cost": 0.1,
                         "complexity_cost": 0.1, "failure_risk": 0.1,
                         "pit_quality": 1.0},
        "legacy_score": {"predictive_contribution": 0.05,
                         "incremental_alpha": 0.0, "stability": 0.1,
                         "correlation": 0.8, "data_cost": 0.3,
                         "complexity_cost": 0.2, "failure_risk": 0.4,
                         "pit_quality": 0.8},
    }


def test_feature_pruning():
    r = feature_pruning(_features())
    assert r["features"]["wave_quality"]["verdict"] == "KEEP"
    assert r["features"]["legacy_score"]["verdict"] == "RETIRE"
    assert "legacy_score" in r["retire_candidates"]
