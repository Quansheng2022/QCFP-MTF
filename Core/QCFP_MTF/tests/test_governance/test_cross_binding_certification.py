# coding: utf-8
"""Certification Cross-Binding 测试（PWC-1 第 4 项）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.certified_decision import certify_decision
from QCFP_MTF.decision.decision_snapshot import DecisionSnapshot


def _snap(release_id="REL-A", manifest_hash="MH-A",
          evidence_pack_hash="EH-A"):
    return DecisionSnapshot(
        decision_id="d1", stock_code="01951", decision_date="2026-08-21",
        institutional_state="ACCUMULATION",
        institutional_permission="ALLOW", permission_cap="TRADE",
        exit_event_kind="NONE", exit_event_reason="", setup_type="BREAKOUT",
        prev_fsm_state="FLAT", next_fsm_state="TESTING",
        previous_position=0.0, target_position=0.2,
        release_id=release_id, release_manifest_hash=manifest_hash,
        evidence_pack_hash=evidence_pack_hash,
        primary_reason="WAVE_CONFIRM",
        context={})


def _manifest(release_id="REL-A", manifest_hash="MH-A"):
    return {"release_id": release_id, "manifest_hash": manifest_hash}


def _pack(release_id="REL-A", evidence_hash="EH-A"):
    return {"release_id": release_id, "evidence_hash": evidence_hash,
            "certification": "CERTIFIED"}


def _ev():
    return {"status": "PASS"}


def _all():
    return {"pit_certificate": _ev(), "ledger_verification": _ev(),
            "replay_certificate": _ev(), "governance_proof": _ev(),
            "production_acceptance": _ev(), "safety_status": "NORMAL"}


def test_same_release_certified():
    r = certify_decision(_snap(), release_manifest=_manifest(),
                         evidence_pack=_pack(), **_all())
    assert r["certified"] is True


def test_snapshot_manifest_mismatch_refused():
    r = certify_decision(_snap(release_id="REL-A"),
                         release_manifest=_manifest(release_id="REL-B"),
                         evidence_pack=_pack(), **_all())
    assert r["refused"] is True
    assert "RELEASE_ID_MISMATCH" in r["failures"]


def test_manifest_pack_mismatch_refused():
    r = certify_decision(_snap(),
                         release_manifest=_manifest(release_id="REL-A"),
                         evidence_pack=_pack(release_id="REL-B"),
                         **_all())
    assert "EVIDENCE_PACK_RELEASE_MISMATCH" in r["failures"]


def test_manifest_hash_mismatch_refused():
    r = certify_decision(_snap(manifest_hash="MH-A"),
                         release_manifest=_manifest(manifest_hash="MH-B"),
                         evidence_pack=_pack(), **_all())
    assert "MANIFEST_HASH_MISMATCH" in r["failures"]


def test_evidence_hash_mismatch_refused():
    r = certify_decision(_snap(evidence_pack_hash="EH-A"),
                         release_manifest=_manifest(),
                         evidence_pack=_pack(evidence_hash="EH-B"),
                         **_all())
    assert "EVIDENCE_HASH_MISMATCH" in r["failures"]
