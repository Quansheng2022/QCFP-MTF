# coding: utf-8
"""certify_decision 绝对 fail-closed 验收（Convergence 新 1 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.certified_decision import certify_decision
from QCFP_MTF.decision.decision_snapshot import DecisionSnapshot


def _snap():
    return DecisionSnapshot(
        decision_id="d1", stock_code="01951", decision_date="2026-08-21",
        institutional_state="ACCUMULATION",
        institutional_permission="ALLOW", permission_cap="TRADE",
        exit_event_kind="NONE", exit_event_reason="", setup_type="BREAKOUT",
        prev_fsm_state="FLAT", next_fsm_state="TESTING",
        previous_position=0.0, target_position=0.2,
        primary_reason="WAVE_CONFIRM", context={})


def _ev(status="PASS"):
    return {"status": status}


def _release():
    return {"release_id": "REL-1", "manifest_hash": "MH1"}


def _pack():
    return {"evidence_hash": "EH1", "certification": "CERTIFIED"}


def _all():
    return {"pit_certificate": _ev(), "ledger_verification": _ev(),
            "replay_certificate": _ev(), "governance_proof": _ev(),
            "production_acceptance": _ev(), "safety_status": "NORMAL",
            "release_manifest": _release(), "evidence_pack": _pack()}


def test_no_evidence_refused():
    assert certify_decision(_snap())["refused"] is True


def test_missing_pit_refused():
    ev = _all()
    ev["pit_certificate"] = None
    assert certify_decision(_snap(), **ev)["refused"] is True


def test_replay_unknown_refused():
    ev = _all()
    ev["replay_certificate"] = _ev("UNKNOWN")
    assert certify_decision(_snap(), **ev)["refused"] is True


def test_acceptance_rejected_refused():
    ev = _all()
    ev["production_acceptance"] = _ev("REJECTED")
    assert certify_decision(_snap(), **ev)["refused"] is True


def test_evidence_pack_missing_refused():
    ev = _all()
    ev["evidence_pack"] = None
    assert certify_decision(_snap(), **ev)["refused"] is True


def test_release_mismatch_refused():
    ev = _all()
    ev["release_manifest"] = {"release_id": ""}
    assert certify_decision(_snap(), **ev)["refused"] is True


def test_all_pass_certified():
    r = certify_decision(_snap(), **_all())
    assert r["certified"] is True
    assert r["certificate"].release_id == "REL-1"
    assert r["certificate"].evidence_pack_hash == "EH1"
    assert r["certificate"].release_manifest_hash == "MH1"
