# coding: utf-8
"""Release / Promotion Gate 测试（40 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.promotion_gate import (PROMOTION_STEPS,
                                                PromotionGateError,
                                                assert_promotion_gate,
                                                promote_release_status,
                                                promotion_gate,
                                                promotion_to_md)


def _all_pass():
    return {step: True for step in PROMOTION_STEPS}


def test_promotion_gate_all_pass():
    r = promotion_gate("v2.0", _all_pass())
    assert r.passed is True
    assert r.release_status == "PRODUCTION"


def test_promotion_gate_fails_on_missing():
    checks = _all_pass()
    checks["oos"] = False
    r = promotion_gate("v2.0", checks)
    assert r.passed is False
    assert "oos" in r.failed
    try:
        assert_promotion_gate("v2.0", checks)
        raise AssertionError("should raise")
    except PromotionGateError:
        pass


def test_release_ladder_no_regress():
    assert promote_release_status("EXPERIMENTAL", "VALIDATED") == "VALIDATED"
    assert promote_release_status("VALIDATED", "SHADOW") == "SHADOW"
    try:
        promote_release_status("PRODUCTION", "SHADOW")
        raise AssertionError("should raise")
    except PromotionGateError:
        pass


def test_promotion_to_md():
    md = promotion_to_md(promotion_gate("v2.0", _all_pass()))
    assert "Promotion Gate" in md
    assert "PROMOTE" in md
