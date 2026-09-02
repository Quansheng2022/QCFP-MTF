# coding: utf-8
"""Rule Ownership Registry 测试（72 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.rule_ownership import DEFAULT_RULE_OWNERS, \
    assert_single_owner, rule_ownership_check


def test_default_owners_defined():
    assert DEFAULT_RULE_OWNERS["final_target"] == "Governance"
    assert DEFAULT_RULE_OWNERS["permission_upper_bound"] == \
        "PermissionPolicy"


def test_single_owner_ok():
    r = rule_ownership_check({
        "final_target": {"owner": "Governance",
                         "implementations": ["Governance"]}})
    assert r["single_owner"] is True
    assert r["violations"] == []


def test_duplicate_authority_detected():
    r = rule_ownership_check({
        "final_target": {"owner": "Governance",
                         "implementations": ["Governance",
                                             "ReportSizing"]}})
    assert r["single_owner"] is False
    assert "final_target" in r["violations"]


def test_assert_single_owner():
    r = assert_single_owner("final_target", "Governance",
                            ["Governance", "ReportSizing"])
    assert r["duplicate_authority"] is True
    assert r["verdict"] == "DUPLICATE_AUTHORITY"
    r2 = assert_single_owner("final_target", "Governance",
                             ["Governance", "Governance"])
    assert r2["verdict"] == "SINGLE_OWNER"


def test_owner_missing_detected():
    r = rule_ownership_check({
        "wave_lifecycle": {"owner": "WaveStagePolicy",
                           "implementations": ["OtherPolicy"]}})
    assert "wave_lifecycle" in r["violations"]
