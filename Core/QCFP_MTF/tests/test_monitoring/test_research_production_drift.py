# coding: utf-8
"""Research-Production Drift 测试（37 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.monitoring.research_production_drift import \
    research_production_drift


def test_low_drift():
    r = research_production_drift({"ACTIVE": 0.5, "MATURE": 0.5},
                                  {"ACTIVE": 0.5, "MATURE": 0.5})
    assert r["severity"] == "LOW"
    assert r["action"] == "CONTINUE"


def test_high_drift_review_only():
    r = research_production_drift(
        {"ACTIVE": 0.8, "MATURE": 0.1, "DECAY": 0.1},
        {"ACTIVE": 0.1, "MATURE": 0.1, "DECAY": 0.8})
    assert r["severity"] == "HIGH_DRIFT"
    assert r["action"] == "REVIEW_ONLY"
    assert r["auto_retrain_forbidden"] is True
    assert "SHADOW" in r["governance_chain"]
    assert "HUMAN_APPROVAL" in r["governance_chain"]
