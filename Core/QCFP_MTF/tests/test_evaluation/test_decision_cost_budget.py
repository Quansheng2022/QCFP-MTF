# coding: utf-8
"""Decision Cost Budget 测试（53 号：决策负担预算）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.evaluation.decision_cost_budget import \
    compare_versions_for_retail, decision_cost_budget


def _low_burden():
    return {"decisions_per_week": 2, "position_changes_per_month": 3,
            "simultaneous_positions": 3, "binding_reasons": 1,
            "manual_attention_events": 2, "emergency_actions": 0}


def _high_burden():
    return {"decisions_per_week": 15, "position_changes_per_month": 20,
            "simultaneous_positions": 12, "binding_reasons": 6,
            "manual_attention_events": 15, "emergency_actions": 8}


def test_low_burden_within_budget():
    r = decision_cost_budget(_low_burden())
    assert r["within_budget"] is True
    assert r["burden_level"] == "LOW"
    assert r["burden_score"] >= 8


def test_high_burden_over_budget():
    r = decision_cost_budget(_high_burden())
    assert r["within_budget"] is False
    assert r["burden_level"] == "HIGH"
    assert r["over_budget"]


def test_compare_prefers_lower_burden_when_oos_similar():
    r = compare_versions_for_retail(
        {"version": "vA", "oos_sharpe": 0.80, "decision_cost": _low_burden()},
        {"version": "vB", "oos_sharpe": 0.82, "decision_cost": _high_burden()},
        oos_similar=True)
    assert r["preferred"] == "vA"
    assert "Burden" in r["reason"] or "负担" in r["reason"]


def test_compare_prefers_higher_sharpe_when_oos_differs():
    r = compare_versions_for_retail(
        {"version": "vA", "oos_sharpe": 0.30, "decision_cost": _low_burden()},
        {"version": "vB", "oos_sharpe": 1.20, "decision_cost": _high_burden()},
        oos_similar=False)
    assert r["preferred"] == "vB"
