# coding: utf-8
"""Counterfactual 接真实 Ledger+Outcome 测试（新 54 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.decision_snapshot import DecisionSnapshot
from QCFP_MTF.evaluation.counterfactual_audit import \
    counterfactual_from_snapshot


def _snap():
    return DecisionSnapshot(
        decision_id="d1", stock_code="01951", decision_date="2026-08-21",
        institutional_state="ACCUMULATION",
        institutional_permission="ALLOW", permission_cap="TRADE",
        exit_event_kind="NONE", exit_event_reason="", setup_type="BREAKOUT",
        prev_fsm_state="FLAT", next_fsm_state="TESTING",
        previous_position=0.0, target_position=0.08,
        raw_target_position=0.40, binding_constraint="liquidity_cap",
        constraint_trace={"steps": [
            {"constraint": "raw_target", "output_value": 0.40,
             "input_value": 0.40},
            {"constraint": "liquidity_cap", "output_value": 0.08,
             "input_value": 0.40}]})


def test_counterfactual_from_snapshot():
    a = counterfactual_from_snapshot(_snap(), outcome=0.10)
    assert a["binding_constraint"] == "liquidity_cap"
    assert a["counterfactuals"]["liquidity_cap"]["without"] == 0.40
    assert a["evidence_store"] == "RESEARCH_EVIDENCE_STORE"
    assert a["cannot_modify_ledger"] is True
    assert a["research_only"] is True
