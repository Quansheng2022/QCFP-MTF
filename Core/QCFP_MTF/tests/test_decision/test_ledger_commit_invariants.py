# coding: utf-8
"""Ledger Commit Invariant Gate 测试（PWC-1 第 6 项）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.decision_ledger import LedgerCommitRejected, \
    assert_snapshot_commit_invariants
from QCFP_MTF.decision.decision_snapshot import DecisionSnapshot


def _snap(action="ENTRY", target=0.04, prev=0.0, fsm=0.10, wave=0.05,
          pit="B", release_id="REL-1", manifest_hash="MH1"):
    return DecisionSnapshot(
        decision_id="d1", stock_code="01951", decision_date="2026-08-21",
        institutional_state="ACCUMULATION",
        institutional_permission="ALLOW", permission_cap="TRADE",
        exit_event_kind="NONE", exit_event_reason="", setup_type="BREAKOUT",
        prev_fsm_state="FLAT", next_fsm_state="TESTING",
        previous_position=prev, target_position=target,
        fsm_proposal_target=fsm, wave_proposal_target=wave,
        canonical_action=action, pit_grade=pit,
        release_id=release_id, release_manifest_hash=manifest_hash,
        primary_reason="WAVE_CONFIRM", context={})


def test_commit_ok_production():
    r = assert_snapshot_commit_invariants(
        _snap(), mode="production",
        permission_cap=0.5, hard_caps={"liquidity_cap": 0.5})
    assert r["verdict"] == "COMMIT_OK"


def test_wrong_action_rejected_production():
    try:
        assert_snapshot_commit_invariants(
            _snap(action="ADD"), mode="production")
        raise AssertionError("should raise")
    except LedgerCommitRejected:
        pass


def test_missing_release_identity_rejected_production():
    try:
        assert_snapshot_commit_invariants(
            _snap(release_id=""), mode="production")
        raise AssertionError("should raise")
    except LedgerCommitRejected as e:
        assert "I6_RELEASE_ID" in str(e)


def test_research_mode_allows():
    r = assert_snapshot_commit_invariants(
        _snap(action="ADD", release_id=""))
    assert r["verdict"] == "RESEARCH_ALLOWED"


def test_wave_monotonicity_violation():
    try:
        assert_snapshot_commit_invariants(
            _snap(target=0.1, fsm=0.1, wave=0.05),
            mode="production")
        raise AssertionError("should raise")
    except LedgerCommitRejected as e:
        assert "I2_WAVE_MONOTONICITY" in str(e)
