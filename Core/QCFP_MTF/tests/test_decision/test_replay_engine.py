# coding: utf-8
"""Deterministic Replay Engine 测试（43 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.decision_snapshot import DecisionSnapshot
from QCFP_MTF.decision.replay_engine import field_by_field_compare, \
    replay_to_md


def _snap(target=0.04, perm="ALLOW", setup="BREAKOUT", fsm="TESTING",
          exit_ev="NONE", reason="WAVE_CONFIRM", raw=0.10, action="ADD"):
    return DecisionSnapshot(
        decision_id="d1", stock_code="01951", decision_date="2026-08-21",
        institutional_state="ACCUMULATION",
        institutional_permission=perm, permission_cap="TRADE",
        exit_event_kind=exit_ev, exit_event_reason="", setup_type=setup,
        prev_fsm_state="FLAT", next_fsm_state=fsm,
        previous_position=0.0, target_position=target,
        raw_target_position=raw, participation_mode="EXPLORE",
        participation_cap=0.10, primary_reason=reason,
        context={"action": action})


def test_exact_match():
    r = field_by_field_compare(_snap(), _snap())
    assert r.status == "EXACT_MATCH"
    assert r.mismatches == ()


def test_mismatch_detected_even_same_target():
    # 决策链改变（wave 不同）但 final target 恰好相同 → 仍 REPLAY_MISMATCH
    orig = _snap(setup="BREAKOUT", target=0.03)
    replay = _snap(setup="PULLBACK", target=0.03)
    r = field_by_field_compare(orig, replay)
    assert r.status == "REPLAY_MISMATCH"
    assert any(m["field"] == "setup_type" for m in r.mismatches)


def test_mismatch_reason_and_action():
    orig = _snap(action="ADD", reason="WAVE_CONFIRM")
    replay = _snap(action="WAIT", reason="ENTRY_LATE")
    r = field_by_field_compare(orig, replay)
    assert r.status == "REPLAY_MISMATCH"
    fields = {m["field"] for m in r.mismatches}
    assert "action" in fields and "primary_reason" in fields


def test_replay_to_md():
    md = replay_to_md(field_by_field_compare(_snap(), _snap()))
    assert "EXACT_MATCH" in md
