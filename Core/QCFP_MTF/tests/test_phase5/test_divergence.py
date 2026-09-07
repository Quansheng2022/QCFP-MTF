# coding: utf-8
"""P5-E / WP5.2 — Canonical-vs-Shadow divergence dedicated tests."""

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
    }
    data.update(overrides)
    return data


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


def test_dx_fail_safe_on_missing_evidence():
    result = dv.classify_divergence({}, _shadow())
    assert result["code"] == "DX"
    assert result["severity"] == "CRITICAL"


def test_dx_on_identity_contradiction():
    result = dv.classify_divergence(
        _canonical(decision_id="D-1"),
        _shadow(decision_id="D-9"))
    assert result["code"] == "DX"
    assert result["severity"] == "CRITICAL"


def test_contract_carrier_uses_frozen_divergence_contract():
    contract = dv.build_divergence_contract(
        _canonical(institutional_permission="BLOCK"),
        _shadow(),
        review_state="DETECTED",
    )
    assert contract["schema_name"] == "DivergenceContract"
    assert contract["schema_version"] == 1
    assert contract["reason_code"] == "D4_GOVERNANCE_INTERCEPTION"
    assert contract["diverged"] is True
    assert contract["severity"] == "LOW"
    assert contract["review_state"] == "DETECTED"


def test_inputs_are_immutable():
    canonical = _canonical(institutional_permission="BLOCK")
    shadow = _shadow()
    canonical_before = copy.deepcopy(canonical)
    shadow_before = copy.deepcopy(shadow)
    _ = dv.classify_divergence(canonical, shadow)
    _ = dv.build_divergence_contract(canonical, shadow)
    assert canonical == canonical_before
    assert shadow == shadow_before


def test_review_lifecycle_valid_path():
    state = dv.advance_review_state(
        "DETECTED", "CLASSIFIED", severity="MEDIUM")
    state = dv.advance_review_state(
        state, "EXPLAINED", severity="MEDIUM")
    state = dv.advance_review_state(state, "REPLAYED", severity="MEDIUM")
    state = dv.advance_review_state(state, "REVIEWED", severity="MEDIUM")
    assert dv.advance_review_state(
        state, "CLOSED", severity="MEDIUM") == "CLOSED"


@pytest.mark.parametrize(
    "current,target",
    [
        ("DETECTED", "CLOSED"),
        ("CLASSIFIED", "CLOSED"),
        ("ESCALATED", "CLOSED"),
        ("DETECTED", "EXPLAINED"),
    ],
)
def test_review_lifecycle_illegal_transitions(current, target):
    with pytest.raises(dv.DivergenceError):
        dv.advance_review_state(
            current, target, severity="MEDIUM")


def test_critical_cannot_auto_close():
    with pytest.raises(dv.DivergenceError):
        dv.advance_review_state(
            "REVIEWED", "CLOSED", severity="CRITICAL")


def test_no_aggregate_score_and_no_authority():
    result = dv.classify_divergence(
        _canonical(institutional_permission="BLOCK"), _shadow())
    sev = dv.divergence_severity(result)
    assert sev["severity"] in dv.DIVERGENCE_SEVERITIES
    assert isinstance(sev["severity"], str)
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


def _shadow_evaluator(payload):
    return {"decision": "SHADOW", "symbol": payload.get("symbol"),
            "target": 0.1}


def test_replay_divergence_match(store):
    runtime = ShadowRuntime(store, evaluator=_shadow_evaluator)
    original = runtime.execute(
        mode="SHADOW", input_payload={"symbol": "00700"},
        evaluation_timestamp=TS, **_identity_kwargs())
    outcome = dv.replay_divergence(
        store, original["shadow_run_id"], _shadow_evaluator,
        expected=_identity_kwargs())
    assert outcome["replay_status"] == "MATCH"
    assert outcome["review_state"] == "REPLAYED"


def test_replay_divergence_mismatch_escalates(store):
    runtime = ShadowRuntime(store, evaluator=_shadow_evaluator)
    original = runtime.execute(
        mode="SHADOW", input_payload={"symbol": "00700"},
        evaluation_timestamp=TS, **_identity_kwargs())
    bad_expected = dict(_identity_kwargs())
    bad_expected["canonical_baseline_id"] = "WRONG"
    outcome = dv.replay_divergence(
        store, original["shadow_run_id"], _shadow_evaluator,
        expected=bad_expected)
    assert outcome["replay_status"] == "MISMATCH"
    assert outcome["severity"] == "CRITICAL"
    assert outcome["review_state"] == "ESCALATED"
