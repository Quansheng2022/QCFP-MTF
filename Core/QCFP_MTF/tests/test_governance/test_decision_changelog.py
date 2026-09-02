# coding: utf-8
"""Decision Impact Changelog 测试（46 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.decision_changelog import decision_changelog


def test_changelog_transition_breakdown():
    r = decision_changelog("v1", "v2",
                           [("收紧 liquidity cap", 100)],
                           {"HOLD->EXIT": 20})
    assert r["total_affected"] == 100
    assert r["transition_breakdown"]["HOLD->EXIT"] == 20
    assert r["no_change_ratio"] == 0.8
    assert r["requires_decision_diff_report"] is True


def test_changelog_empty_no_op():
    r = decision_changelog("v1", "v2", [], {})
    assert r["total_affected"] == 0
    assert r["no_change_ratio"] == 1.0
    assert r["requires_decision_diff_report"] is False


def test_changelog_multiple_changes():
    r = decision_changelog("v1", "v2",
                           [("A", 30), ("B", 70)],
                           {"ADD->HOLD": 25, "HOLD->EXIT": 15})
    assert r["total_affected"] == 100
    assert r["no_change_ratio"] == 0.6
    assert len(r["changes"]) == 2
