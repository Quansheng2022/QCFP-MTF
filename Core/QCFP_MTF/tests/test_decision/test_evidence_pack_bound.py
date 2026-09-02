# coding: utf-8
"""ProductionEvidencePack 绑定测试（新 14 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.certified_decision import CertifiedDecision, \
    assert_evidence_pack_bound, certify_decision
from QCFP_MTF.decision.decision_snapshot import DecisionSnapshot
from QCFP_MTF.governance.production_evidence_pack import \
    EVIDENCE_PACK_FIELDS, production_evidence_pack


def _snap():
    return DecisionSnapshot(
        decision_id="d1", stock_code="01951", decision_date="2026-08-21",
        institutional_state="ACCUMULATION",
        institutional_permission="ALLOW", permission_cap="TRADE",
        exit_event_kind="NONE", exit_event_reason="", setup_type="BREAKOUT",
        prev_fsm_state="FLAT", next_fsm_state="TESTING",
        previous_position=0.0, target_position=0.2,
        primary_reason="WAVE_CONFIRM", context={})


def test_evidence_pack_bound_to_certified_decision():
    pack = production_evidence_pack(
        "REL-001", {f: f"ref-{f}" for f in EVIDENCE_PACK_FIELDS})
    r = certify_decision(
        _snap(),
        pit_certificate={"status": "PASS"},
        ledger_verification={"status": "PASS"},
        replay_certificate={"status": "PASS"},
        governance_proof={"status": "PASS"},
        production_acceptance={"status": "PASS"},
        safety_status="NORMAL",
        release_manifest={"release_id": "REL-001",
                          "manifest_hash": "MH1"},
        evidence_pack=pack)
    assert r["certified"] is True
    cd = r["certificate"]
    assert cd.release_id == "REL-001"
    assert cd.evidence_pack_id == pack["evidence_hash"]
    b = assert_evidence_pack_bound(cd)
    assert b["bound"] is True
    assert b["certification"] == "CERTIFIED"


def test_missing_evidence_pack_not_certified():
    r = certify_decision(_snap())
    assert r["certified"] is False
    cd = CertifiedDecision(
        decision_id="d1", certificate_id="C", snapshot={},
        safety_status="NORMAL", acceptance_verdict="ACCEPTED",
        evidence_ref={}, release_id="")
    b = assert_evidence_pack_bound(cd)
    assert b["bound"] is False
    assert b["certification"] == "NOT_CERTIFIED"
