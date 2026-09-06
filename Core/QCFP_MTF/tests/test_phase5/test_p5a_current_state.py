# coding: utf-8
"""P5-EVID-02 — Single Current Machine State Authority tests."""

import hashlib
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]

STATE_PATH = PROJECT_ROOT / "audit" / "phase5" / "p5a_current_state.json"
ACCEPTANCE_PATH = (
    PROJECT_ROOT / "audit" / "phase5" /
    "checkpoint5a_human_acceptance.json"
)
CORRECTION_PATH = (
    PROJECT_ROOT / "audit" / "phase5" /
    "checkpoint5a_human_acceptance_correction.json"
)

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


def test_human_checkpoint_recorded_accepted():
    p5a = _state()["p5a"]
    assert p5a["checkpoint_5a_status"] == "ACCEPTED"
    assert p5a["checkpoint_5a_human_decision"] == "APPROVE"
    assert p5a["checkpoint_5a_human_required"] is False


def test_p5b_permitted_after_human_acceptance():
    p5a = _state()["p5a"]
    # P5-B01 is only permitted after an explicit Human APPROVE record exists.
    record = _state()["checkpoint5a_acceptance_record"]
    assert record["decision"] == "APPROVE"
    assert record["accepted_by"] == "HUMAN"
    assert p5a["p5b_permitted"] is True
    assert p5a["next_machine_task_after_human_review"] == "P5-B01"


def test_state_revision_is_4():
    assert _state()["state_revision"] == 4


def test_human_acceptance_artifact_exists():
    assert ACCEPTANCE_PATH.exists()


def test_human_artifact_sha_locked():
    record_meta = _state()["checkpoint5a_acceptance_record"]
    assert _sha256(
        "audit/phase5/checkpoint5a_human_acceptance.json"
    ) == record_meta["sha256"]
    assert record_meta["sha256"] == \
        "8012062d0a71761fb4c89b5f29538865ec5f45b4c40825a6fcd4053b7a94273d"


def test_real_human_artifact_parsed():
    """直接解析真实 Human artifact，而非 Current State 复制字段。"""
    actual = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
    assert actual["schema"] == \
        "PHASE5-CHECKPOINT5A-HUMAN-ACCEPTANCE-1"
    assert actual["decision"] == "APPROVE"
    assert actual["accepted_by"] == "HUMAN"
    assert actual["approved_commit"] == \
        "65a604e7da187a67dd08021019a53e6b3da88a4d"


def test_human_approved_input_shas_locked():
    actual = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
    assert actual["acceptance_package_sha256"] == \
        "180ab57a8b0b31ef7263dad5451fccd499ff6216ef9210a9431331ebb5940974"
    assert actual["p5a_r3_evidence_sha256"] == \
        "729de721983ca792b7fa85ddd321a97dc3f8ba637e4feefc2ecbf4aaed5b63a6"
    assert actual["pre_transition_current_state_sha256"] == \
        "e2f741a16d4d5c19711f8ae35c0cc36efa804de30a1d7eb24c2ac466fa67bd63"
    assert actual["review_manifest_sha256"] == \
        "45129313ef31deff5ffe5095149f0dc8cb3f667c6d2a1721a6c4d981b6cc35ab"


def test_correction_artifact_sha_locked():
    assert CORRECTION_PATH.exists()
    record_meta = _state()["checkpoint5a_acceptance_record"]
    correction = record_meta["integrity_correction"]
    assert _sha256(
        "audit/phase5/checkpoint5a_human_acceptance_correction.json"
    ) == correction["sha256"]
    assert correction["sha256"] == \
        "1298f9407c35ca430c0ae72b6b902f6af403675091e8c8a7dc00340c71184b0c"


def test_timestamp_correction_semantics():
    correction = json.loads(CORRECTION_PATH.read_text(encoding="utf-8"))
    ts = correction["timestamp_correction"]
    assert ts["original_value"] == "2026-09-06T21:33:37Z"
    assert ts["normalized_recording_time_utc"] == "2026-09-06T13:33:37Z"
    assert ts["decision_semantics_changed"] is False
    assert correction["original_human_acceptance"]["sha256"] == \
        "8012062d0a71761fb4c89b5f29538865ec5f45b4c40825a6fcd4053b7a94273d"


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
