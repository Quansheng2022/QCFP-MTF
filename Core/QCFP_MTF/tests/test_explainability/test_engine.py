# coding: utf-8
"""Decision Explanation Engine 测试（31 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.decision_snapshot import DecisionSnapshot
from QCFP_MTF.explainability.engine import build_explanation, \
    explanation_to_md


def _snap():
    return DecisionSnapshot(
        decision_id="d1", stock_code="01951", decision_date="2026-08-21",
        institutional_state="ACCUMULATION",
        institutional_permission="ALLOW", permission_cap="TRADE",
        exit_event_kind="NONE", exit_event_reason="", setup_type="BREAKOUT",
        prev_fsm_state="FLAT", next_fsm_state="TESTING",
        previous_position=0.0, target_position=0.04,
        raw_target_position=0.10, participation_mode="EXPLORE",
        participation_cap=0.10, primary_reason="WAVE_CONFIRM",
        context={"governance_proof": {"proof": "PASS"}})


def test_explanation_six_questions():
    exp = build_explanation(
        _snap(), wave_stage="ACTIVE",
        entry_quality={"timing_band": "OPTIMAL"},
        exit_quality={"kind": "NONE"},
        constraint_trace={"reductions": {"liquidity_cap": 0.06}})
    assert len(exp.qa) == 6
    assert "ALLOW" in exp.qa["01_permission"]
    assert "ACTIVE" in exp.qa["02_timing"]
    assert "4.0%" in exp.qa["03_position"]
    assert "限制" in exp.narrative or "执行" in exp.narrative


def test_explanation_exit():
    snap = _snap()
    snap = DecisionSnapshot(
        decision_id="d1", stock_code="01951", decision_date="2026-08-21",
        institutional_state="DISTRIBUTION",
        institutional_permission="BLOCK", permission_cap="FLAT",
        exit_event_kind="HARD_EXIT", exit_event_reason="x",
        setup_type="BREAKOUT", prev_fsm_state="HOLDING",
        next_fsm_state="EXITING", previous_position=0.3,
        target_position=0.0, raw_target_position=0.3,
        participation_mode="STAND", participation_cap=0.0,
        primary_reason="HARD_EXIT",
        context={"governance_proof": {"proof": "PASS"}})
    exp = build_explanation(snap, exit_quality={"kind": "HARD"})
    assert "HARD" in exp.qa["06_exit"]
    assert "不建立新仓" in exp.narrative


def test_explanation_to_md():
    md = explanation_to_md(build_explanation(_snap()))
    assert "Decision Explanation" in md
