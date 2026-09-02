# coding: utf-8
"""Rule Ownership 唯一 Owner 测试（新 72 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.rule_ownership import CANONICAL_RULE_OWNERS, \
    rule_owner_violation_check


def test_canonical_owners_defined():
    assert CANONICAL_RULE_OWNERS["final_target"] == "Governance"
    assert CANONICAL_RULE_OWNERS["permission_upper_bound"] == \
        "PermissionPolicy"
    assert CANONICAL_RULE_OWNERS["historical_fact"] == "Ledger"
    assert len(CANONICAL_RULE_OWNERS) == 9


def test_owner_ok():
    r = rule_owner_violation_check("final_target", "Governance")
    assert r["verdict"] == "OWNER_OK"
    assert r["violation"] is False


def test_owner_violation():
    r = rule_owner_violation_check("final_target", "ReportSizing")
    assert r["verdict"] == "RULE_OWNER_VIOLATION"
    assert r["violation"] is True


def test_unknown_rule_not_violation():
    r = rule_owner_violation_check("unknown_rule", "X")
    assert r["known_rule"] is False
