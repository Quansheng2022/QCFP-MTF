# coding: utf-8
"""Governance Completeness Review 测试（70 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.completeness_review import COMPLETENESS_CHECKS, \
    governance_completeness_review


def _all_closed():
    return {c: "CLOSED" for c in COMPLETENESS_CHECKS}


def test_all_closed_overall():
    r = governance_completeness_review(_all_closed())
    assert r["overall"] == "CLOSED"
    assert r["action_required"] == []
    assert r["mode"] == "长期稳定迭代"


def test_action_required_wins():
    checks = _all_closed()
    checks["mutable_ledger"] = ("ACTION_REQUIRED", "Ledger 可被覆写")
    r = governance_completeness_review(checks)
    assert r["overall"] == "ACTION_REQUIRED"
    assert "mutable_ledger" in r["action_required"]
    assert r["mode"] == "结构收口未完，禁止继续扩张"


def test_accepted_risk_level():
    checks = _all_closed()
    checks["hidden_defaults"] = "ACCEPTED_RISK"
    r = governance_completeness_review(checks)
    assert r["overall"] == "ACCEPTED_RISK"


def test_retire_level():
    checks = _all_closed()
    checks["legacy_default"] = "RETIRE"
    r = governance_completeness_review(checks)
    assert r["overall"] == "RETIRE"


def test_missing_verdict_defaults_action_required():
    checks = _all_closed()
    checks["non_replayable_production_decision"] = None
    r = governance_completeness_review(checks)
    assert r["checks"]["non_replayable_production_decision"][
        "verdict"] == "ACTION_REQUIRED"
