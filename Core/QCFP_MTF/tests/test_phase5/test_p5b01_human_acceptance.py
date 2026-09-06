# coding: utf-8
"""P5-B01-H1R — Human Approval Recording & Gate Closure dedicated tests."""

import hashlib
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]

ACCEPTANCE_PATH = (
    PROJECT_ROOT / "audit" / "phase5" / "p5b01_human_acceptance.json"
)
CLOSURE_PATH = (
    PROJECT_ROOT / "audit" / "phase5" / "p5b01_closure_evidence.json"
)


def _sha256(rel: str) -> str:
    return hashlib.sha256((PROJECT_ROOT / rel).read_bytes()).hexdigest()


def _acceptance() -> dict:
    return json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))


def _closure() -> dict:
    return json.loads(CLOSURE_PATH.read_text(encoding="utf-8"))


def test_human_authority_fields():
    a = _acceptance()
    assert a["decision"] == "APPROVE"
    assert a["accepted_by"] == "HUMAN"
    assert a["decision_source"] == "HUMAN"
    assert a["recorded_by"] == "AI_AGENT"
    assert a["agent_decision_authority"] == "NONE"


def test_identity_binding():
    a = _acceptance()
    assert a["approved_commit"] == \
        "c75110b184ec4deb9baf884d4ec538e927fa7599"
    assert a["review_manifest_sha256"] == \
        "37af687763c61dc67611f3ef8141e4aa731b58df473508b868d6de3cb53fb36d"


def test_acceptance_sha_bound_in_closure_evidence():
    actual = _sha256("audit/phase5/p5b01_human_acceptance.json")
    assert actual == _closure()["human_acceptance_artifact"]["sha256"]


def test_authority_negatives():
    a = _acceptance()
    c = _closure()
    assert a["phase5_pass_authorized"] is False
    assert a["phase6_authorized"] is False
    assert c["phase5_pass_authorized"] is False
    assert c["phase6_authorized"] is False
    assert c["p5_c_started"] is False


def test_governance_immutability():
    assert _sha256(
        "audit/phase5/phase5_governance_baseline.json"
    ) == "0fdc27bbf373653bd98857018ea3013776f721dd4b52776e7a39f486d54904dd"
    assert _sha256(
        "tools/review/merge_project_for_phase5_review.py"
    ) == "44afc41e1790750f53701f19694116c3c364c2be4ac40ef438e7f9f5f633758b"
    assert _sha256(
        "tools/review/tests/test_merge_project_for_phase5_review.py"
    ) == "5133c9d5265e5770700fdcc32c23f88e87e00cddc88e3cfe3716c2418cc3835e"


def test_contract_candidate_not_modified_by_h1r():
    """H1R 只记录 Human 决定；contract candidate c75110b 的 SHA 锚点不变。"""
    assert _closure()["approved_candidate_commit"] == \
        "c75110b184ec4deb9baf884d4ec538e927fa7599"
    assert _closure()["review_manifest_sha256"] == \
        "37af687763c61dc67611f3ef8141e4aa731b58df473508b868d6de3cb53fb36d"
