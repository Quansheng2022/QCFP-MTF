# coding: utf-8
"""Complexity Ceiling Veto 测试（Release 3：新 30 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.complexity_ceiling import \
    AUTHORITY_CEILING_TARGETS, authority_ceiling_check, complexity_veto_release


def _over():
    authorities = dict(AUTHORITY_CEILING_TARGETS)
    authorities["permission_authority"] = 2
    return authority_ceiling_check(authorities)


def test_veto_rejects_without_evidence():
    r = complexity_veto_release(_over(), incremental_value_evidence=False)
    assert r["verdict"] == "RELEASE_REJECTED"
    assert r["allowed"] is False
    assert r["veto"] is True
    assert r["action"] == "SIMPLIFY"


def test_human_review_with_evidence():
    r = complexity_veto_release(_over(), incremental_value_evidence=True)
    assert r["verdict"] == "HUMAN_REVIEW"
    assert r["allowed"] is True


def test_release_ok_within_ceiling():
    ok = authority_ceiling_check(
        {k: v for k, v in AUTHORITY_CEILING_TARGETS.items()})
    r = complexity_veto_release(ok)
    assert r["verdict"] == "RELEASE_OK"
