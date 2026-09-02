# coding: utf-8
"""Complexity Ceiling 测试（60 号：复杂度硬上限）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.complexity_ceiling import complexity_ceiling_check, \
    promotion_decision


def test_within_ceiling_promote_ok():
    usage = {"active_decision_modules": 40, "canonical_decision_stages": 8,
             "decision_critical_parameters": 30,
             "independent_scoring_systems": 4, "duplicate_authorities": 0}
    r = complexity_ceiling_check(usage)
    assert r["within_ceiling"] is True
    assert r["verdict"] == "PROMOTE_OK"


def test_duplicate_authority_over_ceiling():
    usage = {"active_decision_modules": 40, "canonical_decision_stages": 8,
             "decision_critical_parameters": 30,
             "independent_scoring_systems": 4, "duplicate_authorities": 2}
    r = complexity_ceiling_check(usage)
    assert r["within_ceiling"] is False
    assert r["verdict"] == "REJECTED"
    assert "duplicate_authorities" in r["over_ceiling"]


def test_one_in_one_out_allowed():
    r = promotion_decision(["NewGate"], ["LegacyScore"], evidence={})
    assert r["net_added"] == 0
    assert r["verdict"] == "ALLOW"


def test_net_add_three_without_evidence_rejected():
    r = promotion_decision(["A", "B", "C"], [], evidence={})
    assert r["net_added"] == 3
    assert r["verdict"] == "REJECTED"


def test_net_add_three_with_strong_evidence_allowed():
    r = promotion_decision(["A", "B", "C"], [],
                           evidence={"oos": True, "ablation": True,
                                     "stress": True})
    assert r["evidence_strong"] is True
    assert r["verdict"] == "ALLOW"


def test_net_add_one_without_evidence_review():
    r = promotion_decision(["A"], [], evidence={})
    assert r["net_added"] == 1
    assert r["verdict"] == "REVIEW"
