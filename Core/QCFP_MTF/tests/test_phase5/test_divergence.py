# coding: utf-8
"""P5-E-R1 — Divergence semantic repair dedicated tests."""

import copy
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.phase5 import divergence as dv  # noqa: E402
from QCFP_MTF.phase5.shadow_runtime import ShadowRuntime  # noqa: E402
from QCFP_MTF.phase5.shadow_store import ShadowStore  # noqa: E402


TS = "2026-09-07T01:00:00Z"
AS_OF = "2026-09-06T00:00:00Z"


def _canonical(**overrides):
    data = {
        "decision_id": "D-1",
        "source_snapshot_id": "SNAP-1",
        "evidence_pack_id": "EP-1",
        "config_hash": "cfg-1",
        "code_identity": "code-1",
        "rule_version": "R-1",
        "model_version": "M-1",
        "institutional_permission": "ALLOW",
        "next_fsm_state": "HOLD",
        "execution_cap": 1.0,
        "decision_path": ["A", "B"],
        "target_position": 0.1,
        "model_output": "alpha",
    }
    data.update(overrides)
    return data


def _shadow(**overrides):
    data = {
        "decision_id": "D-1",
        "source_snapshot_id": "SNAP-1",
        "evidence_pack_id": "EP-1",
        "config_hash": "cfg-1",
        "code_identity": "code-1",
        "rule_version": "R-1",
        "model_version": "M-1",
        "permission": "ALLOW",
        "fsm_state": "HOLD",
        "execution_cap": 1.0,
        "decision_path": ["A", "B"],
        "target_position": 0.1,
        "model_output": "alpha",
        "shadow_run_id": "SR-1",
    }
    data.update(overrides)
    return data


def _record(state="DETECTED", severity="MEDIUM",
            reason_code="D1_DATA_DELTA", code="D1"):
    return {
        "review_state": state,
        "severity": severity,
        "reason_code": reason_code,
        "code": code,
    }


def _full_evaluator(payload):
    return {
        "rule_version": "R-1",
        "model_version": "M-1",
        "permission": "ALLOW",
        "fsm_state": "HOLD",
        "execution_cap": 1.0,
        "decision_path": ["A", "B"],
        "target_position": 0.1,
        "model_output": "alpha",
    }


def _merge_view(identity: dict, output: dict) -> dict:
    view = {
        "decision_id": identity["decision_id"],
        "source_snapshot_id": identity["source_snapshot_id"],
        "evidence_pack_id": identity["evidence_pack_id"],
        "config_hash": identity["config_hash"],
        "code_identity": identity["code_identity"],
    }
    view.update(output)
    return view


@pytest.mark.parametrize(
    "canonical_overrides,shadow_overrides,expected_code,expected_severity",
    [
        ({}, {}, "D0", "INFO"),
        ({}, {"source_snapshot_id": "SNAP-2"}, "D1", "MEDIUM"),
        ({}, {"evidence_pack_id": "EP-2"}, "D1", "MEDIUM"),
        ({}, {"config_hash": "cfg-2"}, "D2", "MEDIUM"),
        ({}, {"code_identity": "code-2"}, "D3", "MEDIUM"),
        ({"institutional_permission": "BLOCK"}, {"permission": "ALLOW"},
         "D4", "LOW"),
        ({}, {"fsm_state": "EXIT"}, "D5", "HIGH"),
        ({}, {"target_position": 0.2}, "D6", "HIGH"),
        ({}, {"execution_cap": 0.5}, "D7", "MEDIUM"),
        ({}, {"decision_path": ["A", "C"]}, "D8", "HIGH"),
        ({}, {"model_output": "beta"}, "D9", "HIGH"),
    ],
)
def test_taxonomy_positive_cases(
    canonical_overrides, shadow_overrides,
    expected_code, expected_severity,
):
    result = dv.classify_divergence(
        _canonical(**canonical_overrides), _shadow(**shadow_overrides))
    assert result["code"] == expected_code
    assert result["severity"] == expected_severity
    assert result["diverged"] == (expected_code != "D0")
    assert result["reason_code"] == dv.reason_code_for(expected_code)


def test_missing_evidence_does_not_become_d0():
    result = dv.classify_divergence(
        {"decision_id": "D-1"}, {"decision_id": "D-1"})
    assert result["code"] == "DX"
    assert result["severity"] == "CRITICAL"


@pytest.mark.parametrize(
    "field", ["source_snapshot_id", "config_hash", "code_identity",
              "rule_version", "model_version"]
)
def test_missing_required_field_is_dx(field):
    canonical = _canonical()
    shadow = _shadow()
    del canonical[field]
    result = dv.classify_divergence(canonical, shadow)
    assert result["code"] == "DX"
    assert result["severity"] == "CRITICAL"


def test_missing_execution_cap_does_not_become_d0():
    canonical = _canonical()
    shadow = _shadow()
    del canonical["execution_cap"]
    del shadow["execution_cap"]
    result = dv.classify_divergence(canonical, shadow)
    assert result["code"] == "DX"
    assert result["severity"] == "CRITICAL"


def test_missing_execution_cap_single_side_is_dx():
    canonical = _canonical()
    shadow = _shadow()
    del shadow["execution_cap"]
    result = dv.classify_divergence(canonical, shadow)
    assert result["code"] == "DX"
    assert result["severity"] == "CRITICAL"


def test_missing_evidence_does_not_become_d9():
    canonical = {"decision_id": "D-1", "model_output": "alpha"}
    shadow = {"decision_id": "D-1", "model_output": "beta"}
    result = dv.classify_divergence(canonical, shadow)
    assert result["code"] == "DX"


def test_incomplete_evidence_model_output_delta_is_dx():
    canonical = _canonical()
    shadow = _shadow()
    del shadow["fsm_state"]
    shadow["model_output"] = "beta"
    result = dv.classify_divergence(canonical, shadow)
    assert result["code"] == "DX"


def test_dx_on_identity_contradiction():
    result = dv.classify_divergence(
        _canonical(decision_id="D-1"), _shadow(decision_id="D-9"))
    assert result["code"] == "DX"
    assert result["severity"] == "CRITICAL"


def test_contract_carrier_requires_complete_evidence_and_refs():
    contract = dv.build_divergence_contract(
        _canonical(institutional_permission="BLOCK"),
        _shadow(),
        review_state="DETECTED",
    )
    assert contract["schema_name"] == "DivergenceContract"
    assert contract["reason_code"] == "D4_GOVERNANCE_INTERCEPTION"
    assert contract["evidence_refs"] == ["SNAP-1", "SR-1"]


def test_empty_evidence_refs_fail_closed():
    with pytest.raises(dv.DivergenceError):
        dv.build_divergence_contract(_canonical(), _shadow(shadow_run_id=""))
    with pytest.raises(dv.DivergenceError):
        dv.build_divergence_contract(
            _canonical(source_snapshot_id=""), _shadow())


def test_inputs_are_immutable():
    canonical = _canonical(institutional_permission="BLOCK")
    shadow = _shadow()
    c_before = copy.deepcopy(canonical)
    s_before = copy.deepcopy(shadow)
    _ = dv.classify_divergence(canonical, shadow)
    _ = dv.build_divergence_contract(canonical, shadow)
    assert canonical == c_before
    assert shadow == s_before


def test_review_lifecycle_valid_path():
    record = _record("DETECTED", severity="MEDIUM")
    for target in ("CLASSIFIED", "EXPLAINED", "REPLAYED", "REVIEWED",
                   "CLOSED"):
        record["review_state"] = dv.advance_review_state(record, target)
    assert record["review_state"] == "CLOSED"


@pytest.mark.parametrize(
    "state,target",
    [
        ("DETECTED", "CLOSED"),
        ("CLASSIFIED", "CLOSED"),
        ("ESCALATED", "CLOSED"),
        ("DETECTED", "EXPLAINED"),
    ],
)
def test_review_lifecycle_illegal_transitions(state, target):
    with pytest.raises(dv.DivergenceError):
        dv.advance_review_state(_record(state), target)


def test_tampered_dx_record_cannot_close():
    record = {
        "review_state": "REVIEWED",
        "code": "DX",
        "reason_code": "D1_DATA_DELTA",
        "severity": "MEDIUM",
    }
    with pytest.raises(dv.DivergenceError):
        dv.advance_review_state(record, "CLOSED")


def test_tampered_severity_record_fails_closed():
    record = _record(state="REVIEWED", severity="LOW",
                     reason_code="D1_DATA_DELTA", code="D1")
    with pytest.raises(dv.DivergenceError):
        dv.advance_review_state(record, "CLOSED")


def test_critical_record_cannot_be_downgraded_by_caller():
    record = _record("REVIEWED", severity="CRITICAL",
                     reason_code="DX_UNEXPLAINED_DIVERGENCE", code="DX")
    with pytest.raises(dv.DivergenceError):
        dv.advance_review_state(record, "CLOSED")


def test_no_aggregate_score_and_no_authority():
    result = dv.classify_divergence(
        _canonical(institutional_permission="BLOCK"), _shadow())
    sev = dv.divergence_severity(result)
    assert sev["severity"] in dv.DIVERGENCE_SEVERITIES
    assert dv.divergence_blocks(result)["is_authority"] is False


def test_unknown_code_fails_closed():
    with pytest.raises(dv.DivergenceError):
        dv.reason_code_for("Z9")


@pytest.fixture
def store(tmp_path):
    return ShadowStore(tmp_path / "shadow_store")


def _identity_kwargs():
    return {
        "decision_id": "D-1",
        "source_snapshot_id": "SNAP-1",
        "evidence_pack_id": "EP-1",
        "canonical_baseline_id": "BASE-1",
        "shadow_version_id": "SV-1",
        "config_hash": "cfg-1",
        "code_identity": "code-1",
        "as_of_timestamp": AS_OF,
    }


def _original_shadow_view(store, run_id: str) -> dict:
    identity = store.read(run_id)
    decision = store.read_decision(run_id)
    return _merge_view(identity, decision["output"])


def test_replay_divergence_match_reclassifies_same(store):
    runtime = ShadowRuntime(store, evaluator=_full_evaluator)
    original = runtime.execute(
        mode="SHADOW", input_payload={"symbol": "00700"},
        evaluation_timestamp=TS, **_identity_kwargs())
    canonical = _canonical()
    shadow_view = _original_shadow_view(store, original["shadow_run_id"])
    original_result = dv.classify_divergence(canonical, shadow_view)
    outcome = dv.replay_divergence(
        canonical, original_result, store, original["shadow_run_id"],
        _full_evaluator, expected=_identity_kwargs())
    assert outcome["replay_status"] == "MATCH"
    assert outcome["divergence_reproducible"] is True
    assert outcome["review_state"] == "REPLAYED"


def test_replay_divergence_classification_mismatch_escalates(store):
    runtime = ShadowRuntime(store, evaluator=_full_evaluator)
    original = runtime.execute(
        mode="SHADOW", input_payload={"symbol": "00700"},
        evaluation_timestamp=TS, **_identity_kwargs())
    shadow_view = _original_shadow_view(store, original["shadow_run_id"])
    # Original classification used a BLOCK canonical record -> D4.
    canonical_block = _canonical(institutional_permission="BLOCK")
    original_result = dv.classify_divergence(canonical_block, shadow_view)
    assert original_result["code"] == "D4"
    # Replay reclassifies against ALLOW canonical -> D0 mismatch.
    canonical_allow = _canonical()
    outcome = dv.replay_divergence(
        canonical_allow, original_result, store,
        original["shadow_run_id"], _full_evaluator,
        expected=_identity_kwargs())
    assert outcome["replay_status"] == "MISMATCH"
    assert outcome["severity"] == "CRITICAL"
    assert outcome["review_state"] == "ESCALATED"
    assert outcome["reason_code"] == \
        "REPLAY_DIVERGENCE_CLASSIFICATION_MISMATCH"


def test_replay_same_code_different_causal_basis_mismatch(store):
    runtime = ShadowRuntime(store, evaluator=_full_evaluator)
    original = runtime.execute(
        mode="SHADOW", input_payload={"symbol": "00700"},
        evaluation_timestamp=TS, **_identity_kwargs())
    shadow_view = _original_shadow_view(store, original["shadow_run_id"])
    # Original: D1 caused by source_snapshot_id difference.
    canonical_src = _canonical(source_snapshot_id="SNAP-X")
    original_result = dv.classify_divergence(canonical_src, shadow_view)
    assert original_result["code"] == "D1"
    assert "source_snapshot_id" in original_result["changed_fields"]
    # Replay: D1 caused by evidence_pack_id difference (same D-code).
    canonical_pack = _canonical(evidence_pack_id="EP-X")
    outcome = dv.replay_divergence(
        canonical_pack, original_result, store,
        original["shadow_run_id"], _full_evaluator,
        expected=_identity_kwargs())
    assert outcome["replay_status"] == "MISMATCH"
    assert outcome["severity"] == "CRITICAL"
    assert outcome["review_state"] == "ESCALATED"
    assert outcome["reason_code"] == \
        "REPLAY_DIVERGENCE_CLASSIFICATION_MISMATCH"


def test_replay_divergence_shadow_mismatch_escalates(store):
    runtime = ShadowRuntime(store, evaluator=_full_evaluator)
    original = runtime.execute(
        mode="SHADOW", input_payload={"symbol": "00700"},
        evaluation_timestamp=TS, **_identity_kwargs())
    canonical = _canonical()
    shadow_view = _original_shadow_view(store, original["shadow_run_id"])
    original_result = dv.classify_divergence(canonical, shadow_view)
    bad_expected = dict(_identity_kwargs())
    bad_expected["canonical_baseline_id"] = "WRONG"
    outcome = dv.replay_divergence(
        canonical, original_result, store, original["shadow_run_id"],
        _full_evaluator, expected=bad_expected)
    assert outcome["replay_status"] == "MISMATCH"
    assert outcome["reason_code"] == "REPLAY_SHADOW_MISMATCH"
    assert outcome["severity"] == "CRITICAL"
    assert outcome["review_state"] == "ESCALATED"
