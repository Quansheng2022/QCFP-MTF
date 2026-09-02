# coding: utf-8
"""Model Decision Surface Audit 测试（74 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.evaluation.decision_surface_audit import \
    decision_surface_audit


def _perturbations():
    return [
        {"dimension": "evidence_a", "input_delta": 0.01,
         "target_delta": 0.50, "from_target": 0.10, "to_target": 0.60},
        {"dimension": "evidence_b", "input_delta": 0.02,
         "target_delta": 0.05, "from_target": 0.20, "to_target": 0.25},
    ]


def test_jump_detected_and_review():
    r = decision_surface_audit(_perturbations())
    assert r["jump_count"] == 1
    assert r["verdict"] == "REVIEW"
    assert r["auto_smooth_forbidden"] is True
    assert r["surface_stability_index"] == 0.5


def test_stable_surface():
    r = decision_surface_audit([
        {"dimension": "a", "input_delta": 0.02, "target_delta": 0.03},
        {"dimension": "b", "input_delta": 0.03, "target_delta": 0.02},
    ])
    assert r["jump_count"] == 0
    assert r["verdict"] == "STABLE"


def test_large_input_change_not_jump():
    """输入变化本身很大时不算异常跳变。"""
    r = decision_surface_audit([
        {"dimension": "a", "input_delta": 0.30, "target_delta": 0.50}])
    assert r["jump_count"] == 0
