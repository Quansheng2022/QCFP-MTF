# coding: utf-8
"""Release → CertifiedDecision → Ledger 身份链测试（Release 2：新 12 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.decision_snapshot import DecisionSnapshot


def _snap():
    return DecisionSnapshot(
        decision_id="d1", stock_code="01951", decision_date="2026-08-21",
        institutional_state="ACCUMULATION",
        institutional_permission="ALLOW", permission_cap="TRADE",
        exit_event_kind="NONE", exit_event_reason="", setup_type="BREAKOUT",
        prev_fsm_state="FLAT", next_fsm_state="TESTING",
        previous_position=0.0, target_position=0.2,
        release_id="REL-1", release_manifest_hash="MH1")


def test_snapshot_identity_fields():
    s = _snap()
    assert s.release_id == "REL-1"
    assert s.release_manifest_hash == "MH1"
    d = s.as_dict()
    assert d["release_id"] == "REL-1"
    assert d["release_manifest_hash"] == "MH1"


def test_identity_chain_traceable():
    s = _snap()
    assert s.release_id and s.release_manifest_hash
    # decision_id → ReleaseManifest → EvidencePack → ValidationCertificate
    assert s.decision_id
