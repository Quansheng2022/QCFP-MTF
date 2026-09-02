# coding: utf-8
"""Production Feature Manifest 两清单测试（Release 2：新 19 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.decision_snapshot import DecisionSnapshot
from QCFP_MTF.governance.production_feature_manifest import \
    decision_identity_hash, decision_participating_manifest, \
    production_feature_manifest


def _snap():
    return DecisionSnapshot(
        decision_id="d1", stock_code="01951", decision_date="2026-08-21",
        institutional_state="ACCUMULATION",
        institutional_permission="ALLOW", permission_cap="TRADE",
        exit_event_kind="NONE", exit_event_reason="", setup_type="BREAKOUT",
        prev_fsm_state="FLAT", next_fsm_state="TESTING",
        previous_position=0.0, target_position=0.2,
        decision_path=("evidence", "institutional", "wave", "fsm",
                       "sizing", "governance", "final_target"))


def test_participating_manifest_small():
    r = decision_participating_manifest(_snap())
    assert r["count"] <= 8          # 不是全项目 371 个 Feature
    assert r["participating_hash"]
    assert "pit_evidence" in r["participating_features"]


def test_release_manifest_active_only():
    r = production_feature_manifest({"Permission": "ACTIVE",
                                     "NewIdea": "DEFINED"})
    assert r["active_features"] == ["Permission"]


def test_decision_identity_hash():
    h = decision_identity_hash("MH1", "PH1")
    h2 = decision_identity_hash("MH1", "PH2")
    assert h != h2
    assert len(h) == 16
