# coding: utf-8
"""Governance Closeout 1–70 关门检查测试（新 70 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.completeness_review import CLOSEOUT_KEY_ITEMS, \
    governance_closeout


def _all_closed():
    return {k: "CLOSED" for k in CLOSEOUT_KEY_ITEMS}


def test_closeout_enters_maintenance():
    r = governance_closeout(_all_closed(), test_count=359,
                             feature_count=300)
    assert r["closeout"] == "ENTER_LONG_TERM_MAINTENANCE"
    assert r["entered_maintenance"] is True
    assert r["key_items_not_closed"] == []


def test_closeout_not_closed():
    checks = _all_closed()
    checks["mutable_ledger"] = "ACTION_REQUIRED"
    r = governance_closeout(checks)
    assert r["closeout"] == "NOT_CLOSED"
    assert "mutable_ledger" in r["key_items_not_closed"]
    assert r["entered_maintenance"] is False


def test_many_tests_do_not_substitute_closeout():
    checks = _all_closed()
    checks["unexplained_human_override"] = "ACTION_REQUIRED"
    r = governance_closeout(checks, test_count=9999, feature_count=999)
    assert r["closeout"] == "NOT_CLOSED"
    assert "测试数量与 Feature 数量不能替代治理关门" in r["statement"]
