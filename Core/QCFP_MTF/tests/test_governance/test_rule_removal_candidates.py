# coding: utf-8
"""Rule Removal Candidate 测试（新 83 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.rule_removal_test import rule_removal_candidates


def test_candidates_with_validation():
    r = rule_removal_candidates({
        "LegacyCap": {"removal_candidate": True},
        "Permission": {"removal_candidate": False}},
        evidence_ok=True)
    assert r["removal_candidates"] == ["LegacyCap"]
    assert r["validation_required"] == "FULL_VALIDATION"
    assert r["verdict"] == "REMOVAL_GATE_OK"


def test_candidates_blocked_without_evidence():
    r = rule_removal_candidates(
        {"LegacyCap": {"removal_candidate": True}},
        evidence_ok=False)
    assert r["verdict"] == "REMOVAL_GATE_BLOCKED"


def test_no_candidates():
    r = rule_removal_candidates({})
    assert r["verdict"] == "NO_CANDIDATES"
