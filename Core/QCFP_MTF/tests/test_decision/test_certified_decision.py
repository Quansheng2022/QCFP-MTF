# coding: utf-8
"""CertifiedDecision 出口 + Execution Gate 测试（新 6 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.certified_decision import CertifiedDecision, \
    certify_decision
from QCFP_MTF.decision.decision_snapshot import DecisionSnapshot
from QCFP_MTF.execution.execution_gate import ExecutionGateError, execute


def _snap(target=0.2):
    return DecisionSnapshot(
        decision_id="d1", stock_code="01951", decision_date="2026-08-21",
        institutional_state="ACCUMULATION",
        institutional_permission="ALLOW", permission_cap="TRADE",
        exit_event_kind="NONE", exit_event_reason="", setup_type="BREAKOUT",
        prev_fsm_state="FLAT", next_fsm_state="TESTING",
        previous_position=0.0, target_position=target,
        primary_reason="WAVE_CONFIRM", context={"action": "ADD"})


def _evidence(status="PASS"):
    return {"status": status}


def _release():
    return {"release_id": "REL-1", "manifest_hash": "MH1"}


def _pack():
    return {"evidence_hash": "EH1", "certification": "CERTIFIED"}


def _all_evidence():
    return {
        "pit_certificate": _evidence(),
        "ledger_verification": _evidence(),
        "replay_certificate": _evidence(),
        "governance_proof": _evidence(),
        "production_acceptance": _evidence(),
        "safety_status": "NORMAL",
        "release_manifest": _release(),
        "evidence_pack": _pack(),
    }


def test_certified_when_all_ok():
    r = certify_decision(_snap(), **_all_evidence())
    assert r["certified"] is True
    assert r["refused"] is False
    assert isinstance(r["certificate"], CertifiedDecision)
    assert r["certificate"].certificate_id


def test_refused_on_any_gate_failure():
    r = certify_decision(_snap())
    assert r["certified"] is False
    assert r["refused"] is True
    r2 = certify_decision(_snap(), pit_certificate=_evidence("UNKNOWN"),
                          ledger_verification=_evidence("FAIL"))
    assert any("pit_certificate:UNKNOWN" in f for f in r2["failures"])
    assert any("ledger_verification:FAIL" in f for f in r2["failures"])


def test_refused_on_safety_or_acceptance():
    ev = _all_evidence()
    ev["safety_status"] = "SAFE_MODE"
    assert certify_decision(_snap(), **ev)["certified"] is False
    ev2 = _all_evidence()
    ev2["production_acceptance"] = _evidence("REJECTED")
    assert certify_decision(_snap(), **ev2)["certified"] is False


def test_refused_without_evidence_pack():
    ev = _all_evidence()
    ev["evidence_pack"] = None
    r = certify_decision(_snap(), **ev)
    assert r["certified"] is False
    assert any("evidence_pack" in f for f in r["failures"])


def test_refused_on_release_mismatch():
    ev = _all_evidence()
    ev["release_manifest"] = {"release_id": ""}
    r = certify_decision(_snap(), **ev)
    assert r["certified"] is False


def test_execute_rejects_bare_snapshot():
    try:
        execute(_snap())
        raise AssertionError("should raise ExecutionGateError")
    except ExecutionGateError:
        pass


def test_execute_accepts_certified():
    r = certify_decision(_snap(), **_all_evidence())
    out = execute(r["certificate"])
    assert out["executed"] is True
    assert out["certificate_id"] == r["certificate"].certificate_id
