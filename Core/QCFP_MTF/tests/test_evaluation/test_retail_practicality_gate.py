# coding: utf-8
"""Decision Cost Budget 牛散实战门测试（新 53 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.evaluation.decision_cost_budget import \
    retail_practicality_gate


def _low_burden():
    return {"decisions_per_week": 2, "position_changes_per_month": 3,
            "simultaneous_positions": 3, "binding_reasons": 1,
            "manual_attention_events": 2, "emergency_actions": 0}


def _high_burden():
    return {"decisions_per_week": 15, "position_changes_per_month": 20,
            "simultaneous_positions": 12, "binding_reasons": 6,
            "manual_attention_events": 15, "emergency_actions": 8}


def test_prefers_lower_burden_when_oos_close():
    r = retail_practicality_gate([
        {"version": "vA", "oos_sharpe": 0.80,
         "decision_cost": _low_burden()},
        {"version": "vB", "oos_sharpe": 0.82,
         "decision_cost": _high_burden()}])
    assert r["preferred"] == "vA"


def test_empty_candidates():
    assert retail_practicality_gate([])["preferred"] is None
