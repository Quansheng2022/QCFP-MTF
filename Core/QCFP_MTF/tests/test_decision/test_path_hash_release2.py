# coding: utf-8
"""DecisionPathHash Release 2 升级测试（新 13 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.decision_snapshot import DecisionSnapshot
from QCFP_MTF.decision.path_hash import decision_path_hash


def _snap(**kw):
    base = dict(
        decision_id="d1", stock_code="01951", decision_date="2026-08-21",
        institutional_state="ACCUMULATION",
        institutional_permission="ALLOW", permission_cap="TRADE",
        exit_event_kind="NONE", exit_event_reason="", setup_type="BREAKOUT",
        prev_fsm_state="FLAT", next_fsm_state="TESTING",
        previous_position=0.0, target_position=0.08,
        raw_target_position=0.10, binding_constraint="liquidity_cap",
        wave_id="W-1", wave_stage="CONFIRMING", wave_strength=0.8,
        wave_proposal_target=0.05, canonical_action="ENTRY",
        release_id="REL-1", release_manifest_hash="MH1",
        evidence_pack_hash="EH1", data_snapshot_id="DS1",
        universe_snapshot_id="UNI1", model_version="M",
        rule_version="R", settings_hash="cfg1",
        input_fingerprint="fp1", feature_manifest_hash="fmh1",
        context={"governance_proof": {"proof": "PASS"}})
    base.update(kw)
    return DecisionSnapshot(**base)


def test_hash_changes_with_wave_stage():
    a = decision_path_hash(_snap())
    b = decision_path_hash(_snap(wave_stage="ACTIVE"))
    assert a != b


def test_hash_changes_with_final_target():
    a = decision_path_hash(_snap())
    b = decision_path_hash(_snap(target_position=0.2))
    assert a != b


def test_hash_changes_with_release():
    a = decision_path_hash(_snap())
    b = decision_path_hash(_snap(release_manifest_hash="MH2"))
    assert a != b


def test_hash_same_identity_same():
    assert decision_path_hash(_snap()) == decision_path_hash(_snap())
