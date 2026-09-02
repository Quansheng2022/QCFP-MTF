# coding: utf-8
"""Research→Production Drift 生命周期测试（新 37 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.monitoring.research_production_drift import \
    drift_lifecycle_transition, research_production_drift


def test_high_drift_triggers_revalidation():
    r = research_production_drift({"A": 0.9, "B": 0.1},
                                  {"A": 0.1, "B": 0.9})
    assert r["severity"] == "HIGH_DRIFT"
    t = drift_lifecycle_transition(r)
    assert t["lifecycle_state"] == "REVIEW_REQUIRED"
    assert t["revalidation_required"] is True
    assert t["auto_param_modify_forbidden"] is True


def test_moderate_drift_watch():
    r = research_production_drift({"A": 0.65, "B": 0.35},
                                  {"A": 0.35, "B": 0.65})
    t = drift_lifecycle_transition(r)
    assert t["lifecycle_state"] == "WATCH"
    assert t["revalidation_required"] is False


def test_low_drift_normal():
    r = research_production_drift({"A": 0.5, "B": 0.5},
                                  {"A": 0.51, "B": 0.49})
    t = drift_lifecycle_transition(r)
    assert t["lifecycle_state"] == "NORMAL"
