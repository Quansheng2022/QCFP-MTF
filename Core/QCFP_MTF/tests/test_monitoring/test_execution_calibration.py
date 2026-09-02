# coding: utf-8
"""Execution Reality Calibration 测试（45 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.monitoring.execution_calibration import \
    execution_calibration_report, execution_model_error


def test_single_sample_bias_direction():
    assert execution_model_error(0.02, 0.025)["optimistic"] is True
    assert execution_model_error(0.02, 0.015)["pessimistic"] is True
    assert execution_model_error(0.02, 0.021)["optimistic"] is False
    assert execution_model_error(0.02, 0.021)["pessimistic"] is False


def test_zero_estimated_undefined_error():
    r = execution_model_error(0.0, 0.01)
    assert r["error_ratio"] is None
    assert r["optimistic"] is False


def test_calibration_report_optimistic_bias():
    samples = [
        {"dimension": "slippage", "estimated": 0.02, "realized": 0.025},
        {"dimension": "slippage", "estimated": 0.02, "realized": 0.030},
        {"dimension": "exit_days", "estimated": 5, "realized": 3},
    ]
    r = execution_calibration_report(samples)
    assert r["dimensions"]["slippage"]["bias"] == "OPTIMISTIC"
    assert r["dimensions"]["exit_days"]["bias"] == "PESSIMISTIC"
    assert r["research_review_required"] is True
    assert r["auto_param_modify_forbidden"] is True


def test_calibration_report_neutral():
    samples = [{"estimated": 0.02, "realized": 0.021},
               {"estimated": 0.03, "realized": 0.030}]
    r = execution_calibration_report(samples)
    assert r["dimensions"]["slippage"]["bias"] == "NEUTRAL"
    assert r["research_review_required"] is False
