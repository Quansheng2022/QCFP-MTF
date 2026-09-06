# coding: utf-8
"""P5-B01 — Phase 5 Contract Foundation dedicated tests.

Groups:
    * contract shape (required fields / types / enums / schema version)
    * round-trip (object -> serialize -> deserialize -> object)
    * determinism (same logical object -> identical bytes/SHA)
    * negative / fail-closed (missing field, invalid enum/version/timestamp,
      NaN/Infinity, unknown authority state, AUTO_PROMOTED)
    * authority invariants (contract != authority/execution/approval)

Gate: failed = 0, errors = 0, rc = 0 (test count is not a gate).
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.phase5 import contracts as c  # noqa: E402


TS = "2026-09-06T13:33:37Z"
AS_OF = "2026-09-01T00:00:00Z"


def _sample(name: str) -> dict:
    if name == "ShadowRunContract":
        return {
            "schema_name": name,
            "schema_version": 1,
            "shadow_run_id": "SR-1",
            "decision_id": "D-1",
            "source_snapshot_id": "SNAP-1",
            "evidence_pack_id": "EP-1",
            "canonical_baseline_id": "BASE-1",
            "shadow_version_id": "SV-1",
            "evaluation_timestamp": TS,
            "as_of_timestamp": AS_OF,
            "runtime_mode": "SHADOW",
            "config_hash": "abc",
            "code_identity": "code-1",
        }
    if name == "DivergenceContract":
        return {
            "schema_name": name,
            "schema_version": 1,
            "canonical_decision_id": "D-1",
            "shadow_decision_id": "SD-1",
            "diverged": False,
            "severity": "INFO",
            "explanation": "identical",
            "review_state": "OPEN",
            "reason_code": None,
            "evidence_refs": [],
        }
    if name == "OutcomeContract":
        return {
            "schema_name": name,
            "schema_version": 1,
            "decision_id": "D-1",
            "as_of_timestamp": AS_OF,
            "observation_timestamp": TS,
            "horizon": 5,
            "outcome_status": "PENDING",
            "future_return": None,
            "mae": None,
            "mfe": None,
            "evidence_refs": [],
        }
    if name == "AgingContract":
        return {
            "schema_name": name,
            "schema_version": 1,
            "evidence_id": "E-1",
            "observed_at": AS_OF,
            "evaluated_at": TS,
            "policy_version": "aging-v1",
            "aging_state": "FRESH",
            "reason": "within policy",
            "age": None,
        }
    if name == "IncidentContract":
        return {
            "schema_name": name,
            "schema_version": 1,
            "incident_id": "INC-1",
            "incident_type": "REPLAY_MISMATCH",
            "severity": "HIGH",
            "status": "DETECTED",
            "detected_at": TS,
            "human_review_required": True,
            "evidence_refs": [],
            "affected_decisions": [],
            "replay_refs": [],
            "resolution": None,
        }
    if name == "PromotionQualificationContract":
        return {
            "schema_name": name,
            "schema_version": 1,
            "candidate_id": "CAND-1",
            "qualified": False,
            "machine_status": "NOT_QUALIFIED",
            "evaluated_at": TS,
            "gate_results": {},
            "evidence_refs": [],
            "blocking_gates": ["G1"],
        }
    raise KeyError(name)


@pytest.mark.parametrize("schema", c.known_schemas())
def test_contract_shape_and_schema_version(schema):
    assert c.schema_version(schema) == 1
    payload = c.validate_contract_dict(_sample(schema))
    assert payload["schema_name"] == schema
    assert payload["schema_version"] == 1
    for required in c.CONTRACT_DEFINITIONS[schema]["required"]:
        assert required in payload


@pytest.mark.parametrize("schema", c.known_schemas())
def test_roundtrip(schema):
    payload = _sample(schema)
    text = c.serialize_contract(payload)
    restored = c.deserialize_contract(text)
    assert restored == c.validate_contract_dict(payload)


@pytest.mark.parametrize("schema", c.known_schemas())
def test_serialization_determinism(schema):
    payload = _sample(schema)
    first = c.serialize_contract(payload)
    second = c.serialize_contract({k: v for k, v in reversed(list(payload.items()))})
    assert first == second
    assert c.contract_sha256(first) == c.contract_sha256(second)


@pytest.mark.parametrize("schema", c.known_schemas())
def test_missing_required_field_rejected(schema):
    payload = _sample(schema)
    key = c.CONTRACT_DEFINITIONS[schema]["required"][0]
    del payload[key]
    with pytest.raises(c.ContractValidationError):
        c.validate_contract_dict(payload)


@pytest.mark.parametrize("schema", c.known_schemas())
def test_unknown_field_rejected(schema):
    payload = _sample(schema)
    payload["execute"] = True
    with pytest.raises(c.ContractValidationError):
        c.serialize_contract(payload)


def test_invalid_enum_rejected():
    payload = _sample("ShadowRunContract")
    payload["runtime_mode"] = "EXECUTE"
    with pytest.raises(c.ContractValidationError):
        c.validate_contract_dict(payload)


def test_invalid_schema_version_rejected():
    payload = _sample("ShadowRunContract")
    payload["schema_version"] = 2
    with pytest.raises(c.ContractValidationError):
        c.validate_contract_dict(payload)


def test_invalid_timestamp_rejected():
    payload = _sample("ShadowRunContract")
    payload["evaluation_timestamp"] = "2026-09-06 21:33:37"
    with pytest.raises(c.ContractValidationError):
        c.validate_contract_dict(payload)


def test_nan_and_infinity_rejected():
    payload = _sample("OutcomeContract")
    payload["future_return"] = float("nan")
    with pytest.raises(c.ContractValidationError):
        c.validate_contract_dict(payload)
    payload["future_return"] = float("inf")
    with pytest.raises(c.ContractValidationError):
        c.validate_contract_dict(payload)
    with pytest.raises(ValueError):
        c.serialize_contract({**_sample("OutcomeContract"),
                              "future_return": float("nan")})


def test_auto_promoted_rejected():
    payload = _sample("PromotionQualificationContract")
    payload["machine_status"] = "AUTO_PROMOTED"
    with pytest.raises(c.ContractValidationError):
        c.validate_contract_dict(payload)


def test_machine_approval_vocabulary_absent():
    text = c.serialize_contract(_sample("PromotionQualificationContract"))
    for token in ("AUTO_PROMOTED", "PROMOTION_APPROVED_BY_MACHINE",
                  "PROMOTED_TO_PHASE6"):
        assert token not in text


@pytest.mark.parametrize("schema", c.known_schemas())
def test_serialization_is_side_effect_free(schema):
    payload = _sample(schema)
    original = {k: v for k, v in payload.items()}
    _ = c.serialize_contract(payload)
    assert payload == original


def test_contract_is_not_authority_object():
    """契约是数据载体：无 execute/write/promote/approve 方法或字段。"""
    shadow = c.ShadowRunContract(
        shadow_run_id="SR-1", decision_id="D-1",
        source_snapshot_id="SNAP-1", evidence_pack_id="EP-1",
        canonical_baseline_id="BASE-1", shadow_version_id="SV-1",
        evaluation_timestamp=TS, as_of_timestamp=AS_OF,
        runtime_mode="SHADOW", config_hash="abc", code_identity="code-1")
    for method in ("execute", "write_canonical", "promote", "approve"):
        assert not hasattr(shadow, method)
    d = c.contract_dict(shadow)
    assert d["schema_name"] == "ShadowRunContract"
    with pytest.raises(AttributeError):
        shadow.shadow_run_id = "SR-2"


def test_promotion_qualification_carrier_never_approves():
    payload = _sample("PromotionQualificationContract")
    payload["machine_status"] = "QUALIFIED_FOR_HUMAN_REVIEW"
    payload["qualified"] = True
    text = c.serialize_contract(payload)
    assert "QUALIFIED_FOR_HUMAN_REVIEW" in text
    # machine carrier must not contain any approved/promoted state
    for forbidden in c.FORBIDDEN_PROMOTION_STATUSES:
        assert forbidden not in text


def test_outcome_cannot_retroactively_write_decision():
    allowed = set(c._allowed_keys("OutcomeContract"))
    for token in ("decision_outcome", "retroactive", "write_canonical",
                  "authority"):
        assert token not in allowed
