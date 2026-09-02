# coding: utf-8
"""Execution Reality Calibration 降级测试（新 26 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.monitoring.execution_calibration import \
    execution_calibration_downgrade, execution_calibration_report


def test_persistent_optimism_downgrades_certification():
    samples = [
        {"dimension": "slippage", "estimated": 0.02, "realized": 0.025},
        {"dimension": "slippage", "estimated": 0.02, "realized": 0.03},
        {"dimension": "slippage", "estimated": 0.02, "realized": 0.028},
    ]
    report = execution_calibration_report(samples)
    r = execution_calibration_downgrade(report)
    assert r["verdict"] == "CERTIFICATION_DOWNGRADED"
    assert "slippage" in r["optimistic_dimensions"]
    assert r["auto_recalibrate_forbidden"] is True


def test_accurate_model_stable():
    samples = [{"dimension": "slippage", "estimated": 0.02,
                "realized": 0.021},
               {"dimension": "slippage", "estimated": 0.03,
                "realized": 0.03}]
    report = execution_calibration_report(samples)
    r = execution_calibration_downgrade(report)
    assert r["verdict"] == "CERTIFICATION_STABLE"
