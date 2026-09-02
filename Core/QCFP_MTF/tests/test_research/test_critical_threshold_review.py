# coding: utf-8
"""Decision-Critical 阈值 REVIEW 测试（新 63 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.research.threshold_sensitivity_map import \
    DECISION_CRITICAL_THRESHOLDS, critical_threshold_review, \
    threshold_sensitivity_map


def test_critical_thresholds_defined():
    assert "wave_trigger_threshold" in DECISION_CRITICAL_THRESHOLDS
    assert "stop_distance" in DECISION_CRITICAL_THRESHOLDS


def test_cliff_review_not_auto_optimize():
    probes = {"wave_trigger_threshold": {
        0.621: 0.85, 0.6555: 0.84, 0.69: 0.82,
        0.7245: 0.05, 0.759: 0.04}}
    m = threshold_sensitivity_map(probes)
    r = critical_threshold_review(m)
    assert r["verdict"] == "REVIEW"
    assert r["auto_optimize_forbidden"] is True


def test_stable_platform():
    probes = {"position_cap": {
        0.63: 0.80, 0.665: 0.81, 0.70: 0.80,
        0.735: 0.79, 0.77: 0.78}}
    m = threshold_sensitivity_map(probes)
    r = critical_threshold_review(m)
    assert r["verdict"] == "STABLE"
