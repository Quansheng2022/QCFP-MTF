# coding: utf-8
"""Decision Surface Cliff 分类测试（新 74 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.evaluation.decision_surface_audit import cliff_classification


def test_governance_cliff_expected():
    r = cliff_classification({"input_delta": 0.01,
                              "target_delta": 0.5},
                             permission_changed=True)
    assert r["classification"] == "EXPECTED_GOVERNANCE_CLIFF"
    assert r["review_required"] is False


def test_model_cliff_unexpected():
    r = cliff_classification({"input_delta": 0.01,
                              "target_delta": 0.5})
    assert r["classification"] == "UNEXPECTED_MODEL_CLIFF"
    assert r["review_required"] is True


def test_state_flapping():
    r = cliff_classification({"flapping": True})
    assert r["classification"] == "STATE_FLAPPING"


def test_normal():
    r = cliff_classification({"input_delta": 0.02,
                              "target_delta": 0.03})
    assert r["classification"] == "NORMAL"
