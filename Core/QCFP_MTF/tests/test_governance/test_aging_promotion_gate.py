# coding: utf-8
"""Governance Aging 接 Release 测试（新 81 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.governance_aging import aging_promotion_gate


def _rules():
    return {
        "PermissionPolicy": {
            "certified_at": "2026-03",
            "last_revalidated_at": "2026-08"},
        "LiquidityAssumption": {
            "certified_at": "2023-01",
            "last_revalidated_at": "2023-01"},
    }


def test_expired_rule_loses_auto_certification():
    r = aging_promotion_gate(_rules(), as_of="2026-08")
    assert "LiquidityAssumption" in r["lost_auto_certification"]
    assert r["release_verdict"] == "PROMOTION_BLOCKED"
    assert r["allowed"] is False


def test_fresh_rules_allow_promotion():
    r = aging_promotion_gate(
        {"PermissionPolicy": {"certified_at": "2026-03",
                              "last_revalidated_at": "2026-08"}},
        as_of="2026-08")
    assert r["allowed"] is True
    assert r["release_verdict"] == "PROMOTION_OK"
