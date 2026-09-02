# coding: utf-8
"""Production Feature Manifest 测试（新 17 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.decision_snapshot import DecisionSnapshot
from QCFP_MTF.governance.production_feature_manifest import \
    FEATURE_STATES, participating_features, production_feature_manifest


def _states():
    return {"permission_policy": "ACTIVE", "retail_fsm": "ACTIVE",
            "legacy_score": "RETIRED", "new_idea": "DEFINED",
            "half_wired": "WEIRD"}


def test_only_active_in_manifest():
    r = production_feature_manifest(_states())
    assert r["active_features"] == ["permission_policy", "retail_fsm"]
    assert r["invalid_states"] == ["half_wired"]
    assert r["production_manifest_hash"]


def test_manifest_changes_with_active_set():
    a = production_feature_manifest({"x": "ACTIVE"})
    b = production_feature_manifest({"x": "RETIRED"})
    assert a["production_manifest_hash"] != b["production_manifest_hash"]


def test_participating_features_from_snapshot():
    snap = DecisionSnapshot(
        decision_id="d1", stock_code="01951", decision_date="2026-08-21",
        institutional_state="ACCUMULATION",
        institutional_permission="ALLOW", permission_cap="TRADE",
        exit_event_kind="NONE", exit_event_reason="", setup_type="BREAKOUT",
        prev_fsm_state="FLAT", next_fsm_state="TESTING",
        previous_position=0.0, target_position=0.2,
        decision_path=("evidence", "institutional", "fsm", "governance",
                       "final_target"))
    feats = participating_features(snap)
    assert "pit_evidence" in feats
    assert "institutional_permission" in feats
    assert "governance_finalize" in feats


def test_states_whitelist():
    assert FEATURE_STATES == ("DEFINED", "WIRED", "VALIDATED",
                              "CERTIFIED", "ACTIVE", "RETIRED")
