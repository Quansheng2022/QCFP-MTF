# coding: utf-8
"""Opportunity Funnel 接真实 Ledger 测试（新 67 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.decision_snapshot import DecisionSnapshot
from QCFP_MTF.evaluation.opportunity_funnel import funnel_from_ledger, \
    no_trade_explanation


def _rows():
    return [
        {"stock_code": "A", "pit_grade": "B",
         "institutional_permission": "ALLOW", "wave_stage": "ACTIVE",
         "next_fsm_state": "TESTING", "risk_level": "Low",
         "binding_constraint": "", "final_target": 0.2},
        {"stock_code": "B", "pit_grade": "B",
         "institutional_permission": "BLOCK", "wave_stage": "ACTIVE",
         "next_fsm_state": "FLAT", "risk_level": "High",
         "binding_constraint": "", "final_target": 0.0},
        {"stock_code": "C", "pit_grade": "C",
         "institutional_permission": "ALLOW", "wave_stage": "",
         "next_fsm_state": "FLAT", "risk_level": "Low",
         "binding_constraint": "", "final_target": 0.0},
    ]


def test_funnel_from_ledger():
    f = funnel_from_ledger(_rows())
    assert f["counts"]["universe"] == 3
    assert f["counts"]["pit_valid"] == 2
    assert f["counts"]["permission_eligible"] == 1
    assert f["counts"]["final_trade"] == 1


def _snap(target=0.0, binding="", pit="B"):
    return DecisionSnapshot(
        decision_id="d1", stock_code="01951", decision_date="2026-08-21",
        institutional_state="ACCUMULATION",
        institutional_permission="ALLOW", permission_cap="TRADE",
        exit_event_kind="NONE", exit_event_reason="", setup_type="BREAKOUT",
        prev_fsm_state="FLAT", next_fsm_state="FLAT",
        previous_position=0.0, target_position=target, pit_grade=pit,
        binding_constraint=binding, wave_stage="ACTIVE",
        context={"governance_proof": {"proof": "PASS"}})


def test_no_trade_explanation():
    r = no_trade_explanation(_snap())
    assert r["no_trade"] is True
    assert r["why"]
    assert "binding" in r["why"] or "过滤层" in r["why"]


def test_trade_not_no_trade():
    r = no_trade_explanation(_snap(target=0.2))
    assert r["no_trade"] is False
