# coding: utf-8
"""P5-EVID-02 — Single Current Machine State Authority tests."""

import hashlib
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]

STATE_PATH = PROJECT_ROOT / "audit" / "phase5" / "p5a_current_state.json"

# Pre-task captured immutability anchors (P5-EVID-02 §7.5 / §14).
EXPECTED_SHA = {
    "audit/phase5/p5a_checkpoint.json":
        "40311288592bfbce4415cb0462446588c44333aefee29cbc1c60bbcd760abcb6",
    "audit/phase5/p5_gov_freeze_evidence.json":
        "0ba897695eee6620bc6b7565922c3c7bc65c28b529cb408414ee22db747ffbeb",
    "audit/phase5/phase5_governance_baseline.json":
        "0fdc27bbf373653bd98857018ea3013776f721dd4b52776e7a39f486d54904dd",
    "audit/phase5/phase5_governance_acceptance.json":
        "9307fd57ae6e8b1f78820206f8a796493c1611ea9c2690fc3f9c5c96665a66fa",
    "audit/phase5/frozen_surface_manifest.json":
        "edb531c118e85f51738e37656687c59850763802eb0a12f194a552ef9bf54e75",
    "tools/review/merge_project_for_phase5_review.py":
        "44afc41e1790750f53701f19694116c3c364c2be4ac40ef438e7f9f5f633758b",
    "tools/review/tests/test_merge_project_for_phase5_review.py":
        "5133c9d5265e5770700fdcc32c23f88e87e00cddc88e3cfe3716c2418cc3835e",
}


def _sha256(rel: str) -> str:
    return hashlib.sha256((PROJECT_ROOT / rel).read_bytes()).hexdigest()


def _state() -> dict:
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def test_current_state_artifact_exists():
    assert STATE_PATH.exists()


def test_schema_identity():
    s = _state()
    assert s["schema"] == "PHASE5-P5A-CURRENT-STATE-1"
    assert s["current"] is True
    assert s["authority_role"] == "SINGLE_CURRENT_MACHINE_STATE"


def test_governance_binding_exact():
    g = _state()["governance"]
    assert g["state"] == "PHASE5_GOVERNANCE_FROZEN"
    assert g["revision"] == 7
    assert g["candidate_commit"] == \
        "997181cde302b26d56f02bf505f51b6165430c2b"
    assert g["tag"] == "qcfp-mtf-phase5-governance-v1"
    assert g["baseline_sha256"] == \
        "0fdc27bbf373653bd98857018ea3013776f721dd4b52776e7a39f486d54904dd"


def test_governance_baseline_sha_actual_match():
    actual = _sha256("audit/phase5/phase5_governance_baseline.json")
    assert actual == _state()["governance"]["baseline_sha256"]


def test_human_checkpoint_still_pending():
    p5a = _state()["p5a"]
    assert p5a["checkpoint_5a_status"] == "HOLD"
    assert p5a["checkpoint_5a_human_decision"] == "NOT_YET_MADE"
    assert p5a["checkpoint_5a_human_required"] is True


def test_p5b_hard_prohibition():
    p5a = _state()["p5a"]
    assert p5a["p5b_permitted"] is False
    assert p5a["next_machine_task_after_human_review"] != "P5-B01"


def test_historical_checkpoint_claim_superseded():
    entries = _state()["superseded_current_claims"]
    entry = next(
        e for e in entries
        if e["path"] == "audit/phase5/p5a_checkpoint.json"
    )
    assert entry["current_authority"] is False
    assert entry["status"] == "HISTORICAL_CLAIM_SUPERSEDED"


def test_historical_freeze_procedure_claim_superseded():
    entries = _state()["superseded_current_claims"]
    entry = next(
        e for e in entries
        if e["path"] == "audit/phase5/p5_gov_freeze_evidence.json"
    )
    assert entry["current_authority"] is False
    assert entry["status"] == "HISTORICAL_CLAIM_SUPERSEDED"


def test_historical_files_preserved():
    for rel in (
        "audit/phase5/p5a_checkpoint.json",
        "audit/phase5/p5_gov_freeze_evidence.json",
    ):
        assert _sha256(rel) == EXPECTED_SHA[rel], rel


def test_frozen_governance_preserved():
    for rel in (
        "audit/phase5/phase5_governance_baseline.json",
        "audit/phase5/phase5_governance_acceptance.json",
        "audit/phase5/frozen_surface_manifest.json",
        "tools/review/merge_project_for_phase5_review.py",
        "tools/review/tests/test_merge_project_for_phase5_review.py",
    ):
        assert _sha256(rel) == EXPECTED_SHA[rel], rel
