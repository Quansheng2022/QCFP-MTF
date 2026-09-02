# coding: utf-8
"""Complexity Ceiling 否决 Promotion 测试（新 60 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.complexity_ceiling import AUTHORITY_CEILING_TARGETS, \
    authority_ceiling_check, complexity_promotion_veto


def _over_ceiling():
    authorities = dict(AUTHORITY_CEILING_TARGETS)
    authorities["permission_authority"] = 2
    return authority_ceiling_check(authorities)


def test_over_ceiling_without_evidence_rejected():
    r = complexity_promotion_veto(_over_ceiling(),
                                  incremental_value_evidence=False)
    assert r["verdict"] == "PROMOTION_REJECTED"
    assert r["allowed"] is False


def test_over_ceiling_with_evidence_review():
    r = complexity_promotion_veto(_over_ceiling(),
                                  incremental_value_evidence=True)
    assert r["verdict"] == "PROMOTION_REVIEW"
    assert r["allowed"] is True


def test_within_ceiling_ok():
    ok = authority_ceiling_check(
        {k: v for k, v in AUTHORITY_CEILING_TARGETS.items()})
    r = complexity_promotion_veto(ok)
    assert r["verdict"] == "PROMOTION_OK"
