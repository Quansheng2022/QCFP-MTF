# coding: utf-8
"""Decision Threshold Sensitivity Map 测试（63 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.research.threshold_sensitivity_map import default_probes, \
    threshold_sensitivity_map, threshold_stability_verdict


def test_default_probes_five_points():
    p = default_probes(0.70)
    assert len(p) == 5
    assert 0.63 in p and 0.77 in p


def test_stable_threshold():
    probes = {"permission_threshold": {
        0.63: 0.80, 0.665: 0.81, 0.70: 0.80, 0.735: 0.79, 0.77: 0.78}}
    r = threshold_sensitivity_map(probes)
    assert r["thresholds"]["permission_threshold"]["status"] == "STABLE"
    assert threshold_stability_verdict(r)["verdict"] == "STABLE_INTERVAL"


def test_cliff_detected():
    """0.69 很好、0.70 崩溃 → OVERFIT_RISK。"""
    probes = {"wave_confirmation": {
        0.621: 0.85, 0.6555: 0.84, 0.69: 0.82,
        0.7245: 0.05, 0.759: 0.04}}
    r = threshold_sensitivity_map(probes)
    assert r["thresholds"]["wave_confirmation"]["status"] == "CLIFF"
    v = threshold_stability_verdict(r)
    assert v["verdict"] == "OVERFIT_RISK"
    assert "wave_confirmation" in v["cliff_thresholds"]


def test_no_data_threshold():
    r = threshold_sensitivity_map({"stop_distance": {}})
    assert r["thresholds"]["stop_distance"]["status"] == "NO_DATA"
