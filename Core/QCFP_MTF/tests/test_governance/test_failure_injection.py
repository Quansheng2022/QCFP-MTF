# coding: utf-8
"""Governance Failure Injection Tests（48 号：攻击自己的系统）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.data.feature_contract import assert_decision_layer_features
from QCFP_MTF.data.information_set import PITViolation
from QCFP_MTF.decision.replay_engine import field_by_field_compare
from QCFP_MTF.decision.decision_snapshot import DecisionSnapshot
from QCFP_MTF.governance.feature_gate import FeatureGateError
from QCFP_MTF.governance.release_manifest import (ReleaseManifest,
                                                  ReleaseManifestRegistry)
from QCFP_MTF.report.contract import ReportContractError


def _snap(target=0.04, perm="ALLOW"):
    return DecisionSnapshot(
        decision_id="d1", stock_code="01951", decision_date="2026-08-21",
        institutional_state="ACCUMULATION",
        institutional_permission=perm, permission_cap="TRADE",
        exit_event_kind="NONE", exit_event_reason="", setup_type="BREAKOUT",
        prev_fsm_state="FLAT", next_fsm_state="TESTING",
        previous_position=0.0, target_position=target,
        primary_reason="WAVE_CONFIRM", context={"action": "ADD"})


def test_inject_pit_timestamp_ahead():
    try:
        assert_decision_layer_features(
            {"decision_date": "2026-08-21",
             "structural_available_date": "2026-09-01"},
            decision_time="2026-08-21")
        raise AssertionError("should raise")
    except (FeatureGateError, PITViolation):
        pass


def test_inject_wave_outcome_into_production():
    try:
        assert_decision_layer_features(
            {"wave_label": "W1", "decision_date": "2026-08-21"},
            decision_time="2026-08-21")
        raise AssertionError("should raise")
    except FeatureGateError:
        pass


def test_inject_replay_mismatch():
    r = field_by_field_compare(_snap(target=0.04), _snap(target=0.10))
    assert r.status == "REPLAY_MISMATCH"


def test_inject_implicit_release_conflict():
    reg = ReleaseManifestRegistry()
    m1 = ReleaseManifest(release_id="R1", config_hash="C1", code_commit="A")
    reg.freeze(m1)
    # 相同 config+commit 但不同 release → 隐性版本冲突
    try:
        reg.freeze(ReleaseManifest(release_id="R2", config_hash="C1",
                                   code_commit="A"))
        raise AssertionError("should raise")
    except ValueError:
        pass


def test_inject_report_recomputation():
    from QCFP_MTF.report.contract import assert_report_ledger_only
    ledger = {"institutional_permission": "BLOCK",
              "previous_fsm_state": "FLAT", "next_fsm_state": "TESTING",
              "final_target": 0.0, "primary_reason": "PERMISSION_BLOCK"}
    try:
        assert_report_ledger_only(_snap(), ledger)
        raise AssertionError("should raise")
    except ReportContractError:
        pass
