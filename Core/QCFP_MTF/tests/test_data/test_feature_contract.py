# coding: utf-8
"""Feature Contract 测试（32 号：特征契约防穿透）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.data.feature_contract import (DECISION_FEATURE_CONTRACTS,
                                            assert_evidence_features,
                                            validate_evidence_features,
                                            assert_feature_contract,
                                            validate_feature)
from QCFP_MTF.governance.feature_gate import FeatureGateError


def test_decision_feature_allowed():
    c = DECISION_FEATURE_CONTRACTS["institutional_permission"]
    ok, errs = validate_feature(c, "ALLOW", layer="decision")
    assert ok and not errs
    ok, errs = validate_feature(c, "NOT_A_PERMISSION", layer="decision")
    assert not ok


def test_future_feature_blocked_in_decision():
    c = DECISION_FEATURE_CONTRACTS["future_return"]
    ok, errs = validate_feature(c, 0.5, layer="decision")
    assert not ok
    assert any("FEATURE_GATE" in e for e in errs)
    try:
        assert_feature_contract(c, 0.5, layer="decision")
        raise AssertionError("should raise FeatureGateError")
    except FeatureGateError:
        pass


def test_missing_policy_reject():
    c = DECISION_FEATURE_CONTRACTS["c_state"]
    ok, errs = validate_feature(c, None, layer="decision")
    assert not ok
    assert any("MISSING" in e for e in errs)


def test_range_check():
    c = DECISION_FEATURE_CONTRACTS["q_position_52w"]
    ok, errs = validate_feature(c, 1.5, layer="decision")
    assert not ok and any("RANGE" in e for e in errs)
    ok, errs = validate_feature(c, 0.3, layer="decision")
    assert ok


def test_evidence_batch_validation():
    ev = {"institutional_permission": "ALLOW", "c_state": "C↑",
          "q_position_52w": 0.3, "data_quality": "B"}
    ok, errs = validate_evidence_features(ev)
    assert ok and not errs
    ev_bad = {"future_return": 0.5, "institutional_permission": "ALLOW"}
    try:
        assert_evidence_features(ev_bad)
        raise AssertionError("should raise")
    except FeatureGateError:
        pass
