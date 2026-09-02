# coding: utf-8
"""Confidence Calibration 测试（61 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.monitoring.confidence_calibration import (
    apply_calibration, calibrate_confidence, calibration_curve,
    expected_calibration_error, log_loss)


def _records():
    return [{"confidence": 0.85, "outcome": 1}] * 8 + \
        [{"confidence": 0.85, "outcome": 0}] * 2 + \
        [{"confidence": 0.60, "outcome": 1}] * 6 + \
        [{"confidence": 0.60, "outcome": 0}] * 4


def test_calibration_curve():
    curve = calibration_curve(_records())
    assert "0.55-0.70" in curve
    assert abs(curve["0.55-0.70"]["actual_win_rate"] - 0.6) < 1e-4


def test_calibrate_confidence():
    r = calibrate_confidence(_records(), oos_validated=True)
    assert r["brier_score"] is not None
    assert "0.55-0.70" in r["reliability_curve"]
    assert r["calibrated"] is True
    assert r["calibration_mapping"]


def test_apply_calibration():
    mapping = {0.625: 0.6, 0.925: 0.8}
    assert abs(apply_calibration(0.62, mapping) - 0.6) < 1e-6
    assert apply_calibration(0.62, {}) == 0.62


def test_calibration_requires_oos():
    r = calibrate_confidence(_records(), oos_validated=False)
    assert r["calibrated"] is False
    assert r["calibration_mapping"] == {}


def test_log_loss_23():
    ll = log_loss([0.9, 0.2, 0.8], [1, 0, 1])
    assert ll is not None and ll > 0
    perfect = log_loss([1.0, 0.0], [1, 0])
    assert perfect < ll


def test_ece_23():
    ece = expected_calibration_error(_records(), n_bins=5)
    assert ece["ece"] is not None
    assert 0 <= ece["ece"] <= 1
