# coding: utf-8
"""Risk Reduction Attribution 模块判定测试（新 75 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.evaluation.risk_reduction_attribution import \
    risk_module_verdict


def test_keep_with_risk_reduction():
    r = risk_module_verdict("Permission", 0.09, 0.01, 0.0)
    assert r["verdict"] == "KEEP"


def test_delete_when_no_value_and_duplicate():
    r = risk_module_verdict("ExecutionCap", 0.0, 0.0, 0.1)
    assert r["verdict"] == "DELETE_REVIEW"
    assert r["delete"] is True


def test_review_when_no_reduction():
    r = risk_module_verdict("X", 0.0, 0.03, 0.0)
    assert r["verdict"] == "REVIEW"
