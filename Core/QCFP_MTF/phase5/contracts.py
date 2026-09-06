# coding: utf-8
"""P5-B01 — Phase 5 Contract Foundation (contract layer only).

This module defines *data contracts* used by later Phase 5 work packages
(P5-C Shadow Runtime ... P5-I Promotion Qualification). It deliberately
contains NO runtime behavior:

    * no shadow evaluation / execution
    * no divergence detection / classification
    * no outcome computation or future-data access
    * no aging engine / clock
    * no incident detection
    * no promotion engine / approval

Every contract is a pure, immutable carrier with:
    * schema_name + schema_version
    * stable field list (unknown keys are rejected)
    * UTC timestamps (string, ``...Z``)
    * no NaN / Infinity
    * deterministic serialization (sorted keys, fixed separators)

Identity semantics are REUSED from the frozen system (decision identity,
release identity, ledgers, etc.); this module only references those ids as
opaque strings and never re-defines Canonical Authority.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping


class ContractValidationError(ValueError):
    """Raised when a contract payload violates its schema/invariants."""


def _reject_nan(value: Any) -> Any:
    raise ValueError("NaN / Infinity is forbidden in contract payloads")


UTC_TS_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
)


def _valid_utc(value: str) -> bool:
    if not isinstance(value, str) or not UTC_TS_RE.match(value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return True


def _finite_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        import math

        return math.isfinite(value)
    return False


def _type_matches(value: Any, expected: Any) -> bool:
    """Type check with explicit bool-vs-int disambiguation."""
    if isinstance(expected, tuple):
        if value is None and type(None) in expected:
            return True
        candidates = [t for t in expected if t is not type(None)]
        if int in candidates and isinstance(value, bool):
            return False
        return any(isinstance(value, t) for t in candidates)
    if expected is int and isinstance(value, bool):
        return False
    return isinstance(value, expected)


def _validate_string_sequence(
    name: str, field_name: str, value: Any
) -> None:
    if not isinstance(value, (list, tuple)):
        raise ContractValidationError(
            f"{name}.{field_name}: must be a list/tuple of strings"
        )
    if not all(isinstance(item, str) for item in value):
        raise ContractValidationError(
            f"{name}.{field_name}: every element must be str"
        )


def _validate_string_bool_map(
    name: str, field_name: str, value: Any
) -> None:
    if not isinstance(value, Mapping):
        raise ContractValidationError(
            f"{name}.{field_name}: must be a mapping"
        )
    for key, result in value.items():
        if not isinstance(key, str):
            raise ContractValidationError(
                f"{name}.{field_name}: mapping keys must be str"
            )
        if not isinstance(result, bool):
            raise ContractValidationError(
                f"{name}.{field_name}: mapping values must be bool"
            )


# ---------------------------------------------------------------------------
# Common enums (contract vocabulary only)
# ---------------------------------------------------------------------------

RUNTIME_MODES = ("CANONICAL", "SHADOW", "REPLAY")
FRESHNESS_STATES = (
    "FRESH", "AGING", "STALE", "EXPIRED", "INVALID", "UNKNOWN",
)
DIVERGENCE_SEVERITIES = ("INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL")
INCIDENT_SEVERITIES = ("SEV-0", "SEV-1", "SEV-2", "SEV-3")
OUTCOME_STATUSES = (
    "PENDING", "REALIZED", "MISSING_DATA", "INVALID", "EXPIRED",
)
INCIDENT_STATUSES = (
    "DETECTED", "QUALIFIED", "CONTAINED", "ROOT_CAUSED", "FIXED",
    "REPLAYED", "REGRESSION_TESTED", "CLOSED",
)
PROMOTION_MACHINE_STATUSES = (
    "NOT_EVALUATED", "NOT_QUALIFIED", "QUALIFIED_FOR_HUMAN_REVIEW",
)
FORBIDDEN_PROMOTION_STATUSES = (
    "AUTO_PROMOTED", "PROMOTION_APPROVED_BY_MACHINE",
    "APPROVED", "REJECTED", "HOLD", "REQUEST_MORE_EVIDENCE",
)


def _enum_fields(schema: str) -> dict[str, tuple[str, ...]]:
    return CONTRACT_DEFINITIONS[schema].get("enums", {})


# ---------------------------------------------------------------------------
# Contract definitions (single truth for validation / serialization)
# ---------------------------------------------------------------------------

CONTRACT_DEFINITIONS: dict[str, dict[str, Any]] = {
    "ShadowRunContract": {
        "version": 1,
        "required": (
            "shadow_run_id", "decision_id", "source_snapshot_id",
            "evidence_pack_id", "canonical_baseline_id",
            "shadow_version_id", "evaluation_timestamp", "as_of_timestamp",
            "runtime_mode", "config_hash", "code_identity",
        ),
        "optional": (),
        "enums": {"runtime_mode": RUNTIME_MODES},
        "timestamps": ("evaluation_timestamp", "as_of_timestamp"),
        "types": {
            "shadow_run_id": str, "decision_id": str,
            "source_snapshot_id": str, "evidence_pack_id": str,
            "canonical_baseline_id": str, "shadow_version_id": str,
            "evaluation_timestamp": str, "as_of_timestamp": str,
            "runtime_mode": str, "config_hash": str, "code_identity": str,
        },
        "nonempty_strings": (
            "shadow_run_id", "decision_id", "source_snapshot_id",
            "evidence_pack_id", "canonical_baseline_id",
            "shadow_version_id", "config_hash", "code_identity",
        ),
        "note": (
            "Identity-only shadow run record; no execution/write/promote "
            "capability."
        ),
    },
    "DivergenceContract": {
        "version": 1,
        "required": (
            "canonical_decision_id", "shadow_decision_id", "diverged",
            "severity", "explanation", "review_state",
        ),
        "optional": ("reason_code", "evidence_refs"),
        "enums": {"severity": DIVERGENCE_SEVERITIES},
        "timestamps": (),
        "types": {
            "canonical_decision_id": str, "shadow_decision_id": str,
            "diverged": bool, "severity": str, "explanation": str,
            "review_state": str, "reason_code": (str, type(None)),
            "evidence_refs": (list, tuple),
        },
        "string_sequences": ("evidence_refs",),
        "nonempty_strings": ("canonical_decision_id", "shadow_decision_id"),
        "note": (
            "Canonical-vs-Shadow divergence carrier. Classification "
            "taxonomy/lifecycle belongs to P5-E."
        ),
    },
    "OutcomeContract": {
        "version": 1,
        "required": (
            "decision_id", "as_of_timestamp", "observation_timestamp",
            "horizon", "outcome_status",
        ),
        "optional": (
            "future_return", "mae", "mfe", "evidence_refs",
        ),
        "enums": {"outcome_status": OUTCOME_STATUSES},
        "timestamps": ("as_of_timestamp", "observation_timestamp"),
        "types": {
            "decision_id": str, "as_of_timestamp": str,
            "observation_timestamp": str, "horizon": int,
            "outcome_status": str,
            "future_return": (int, float, type(None)),
            "mae": (int, float, type(None)),
            "mfe": (int, float, type(None)),
            "evidence_refs": (list, tuple),
        },
        "string_sequences": ("evidence_refs",),
        "nonempty_strings": ("decision_id",),
        "note": (
            "Post-decision observation carrier. Never retroactively rewrites "
            "a decision; outcome observation belongs to P5-F."
        ),
    },
    "AgingContract": {
        "version": 1,
        "required": (
            "evidence_id", "observed_at", "evaluated_at",
            "policy_version", "aging_state", "reason",
        ),
        "optional": ("age",),
        "enums": {"aging_state": FRESHNESS_STATES},
        "timestamps": ("observed_at", "evaluated_at"),
        "types": {
            "evidence_id": str, "observed_at": str, "evaluated_at": str,
            "policy_version": str, "aging_state": str, "reason": str,
            "age": (int, float, type(None)),
        },
        "nonempty_strings": ("evidence_id", "policy_version"),
        "note": "Evidence freshness carrier; aging engine belongs to P5-G.",
    },
    "IncidentContract": {
        "version": 1,
        "required": (
            "incident_id", "incident_type", "severity", "status",
            "detected_at", "human_review_required",
        ),
        "optional": (
            "evidence_refs", "affected_decisions", "replay_refs",
            "resolution",
        ),
        "enums": {
            "severity": INCIDENT_SEVERITIES,
            "status": INCIDENT_STATUSES,
        },
        "timestamps": ("detected_at",),
        "types": {
            "incident_id": str, "incident_type": str, "severity": str,
            "status": str, "detected_at": str,
            "human_review_required": bool,
            "evidence_refs": (list, tuple),
            "affected_decisions": (list, tuple),
            "replay_refs": (list, tuple),
            "resolution": (str, type(None)),
        },
        "string_sequences": (
            "evidence_refs", "affected_decisions", "replay_refs",
        ),
        "nonempty_strings": ("incident_id", "incident_type"),
        "note": (
            "Incident carrier. Detection / lifecycle / blocking belong to "
            "P5-H; this carrier never auto-clears an authority blocker."
        ),
    },
    "PromotionQualificationContract": {
        "version": 1,
        "required": (
            "candidate_id", "qualified", "machine_status",
            "evaluated_at",
        ),
        "optional": (
            "gate_results", "evidence_refs", "blocking_gates",
        ),
        "enums": {
            "machine_status": PROMOTION_MACHINE_STATUSES,
        },
        "timestamps": ("evaluated_at",),
        "types": {
            "candidate_id": str, "qualified": bool, "machine_status": str,
            "evaluated_at": str, "gate_results": dict,
            "evidence_refs": (list, tuple),
            "blocking_gates": (list, tuple),
        },
        "string_sequences": ("evidence_refs", "blocking_gates"),
        "string_bool_maps": ("gate_results",),
        "nonempty_strings": ("candidate_id",),
        "note": (
            "Machine qualification carrier only. machine_status max = "
            "QUALIFIED_FOR_HUMAN_REVIEW; promotion approval is Human-only."
        ),
    },
}


def _allowed_keys(schema: str) -> tuple[str, ...]:
    d = CONTRACT_DEFINITIONS[schema]
    return tuple(d["required"]) + tuple(d["optional"]) + (
        "schema_name", "schema_version",
    )


def known_schemas() -> tuple[str, ...]:
    return tuple(CONTRACT_DEFINITIONS)


def schema_version(name: str) -> int:
    if name not in CONTRACT_DEFINITIONS:
        raise ContractValidationError(f"unknown contract schema: {name}")
    return int(CONTRACT_DEFINITIONS[name]["version"])


def validate_contract_dict(data: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize a contract payload; fail closed on any defect."""
    if not isinstance(data, Mapping):
        raise ContractValidationError("contract payload must be a mapping")
    payload = dict(data)
    name = payload.get("schema_name")
    if name not in CONTRACT_DEFINITIONS:
        raise ContractValidationError(
            f"missing/unknown schema_name: {name!r}"
        )
    version = payload.get("schema_version")
    if version != CONTRACT_DEFINITIONS[name]["version"]:
        raise ContractValidationError(
            f"{name}: unsupported schema_version {version!r}"
        )

    definition = CONTRACT_DEFINITIONS[name]
    allowed = set(_allowed_keys(name))
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ContractValidationError(
            f"{name}: unknown field(s) rejected: {unknown}"
        )

    missing = [
        key for key in definition["required"] if key not in payload
    ]
    if missing:
        raise ContractValidationError(
            f"{name}: missing required field(s): {missing}"
        )

    for field_name, allowed_values in definition.get("enums", {}).items():
        value = payload.get(field_name)
        if value not in allowed_values:
            raise ContractValidationError(
                f"{name}.{field_name}: invalid enum {value!r} "
                f"(allowed: {sorted(allowed_values)})"
            )

    for field_name in definition.get("timestamps", ()):
        value = payload.get(field_name)
        if not _valid_utc(value):
            raise ContractValidationError(
                f"{name}.{field_name}: invalid UTC timestamp {value!r}"
            )

    for field_name, expected in definition.get("types", {}).items():
        if field_name in payload and payload[field_name] is not None \
                and not _type_matches(payload[field_name], expected):
            raise ContractValidationError(
                f"{name}.{field_name}: type mismatch "
                f"({payload[field_name]!r} not allowed by {expected!r})"
            )

    for field_name in definition.get("nonempty_strings", ()):
        value = payload.get(field_name)
        if not isinstance(value, str) or value.strip() == "":
            raise ContractValidationError(
                f"{name}.{field_name}: must be a non-empty string"
            )

    for field_name in definition.get("string_sequences", ()):
        if field_name in payload and payload[field_name] is not None:
            _validate_string_sequence(name, field_name, payload[field_name])

    for field_name in definition.get("string_bool_maps", ()):
        if field_name in payload and payload[field_name] is not None:
            _validate_string_bool_map(name, field_name, payload[field_name])

    for field_name in ("future_return", "mae", "mfe", "age"):
        if field_name in payload and payload[field_name] is not None \
                and not _finite_number(payload[field_name]):
            raise ContractValidationError(
                f"{name}.{field_name}: must be finite number, got "
                f"{payload[field_name]!r}"
            )

    for field_name in ("horizon",):
        if field_name in payload and payload[field_name] is not None \
                and (not isinstance(payload[field_name], int)
                     or payload[field_name] <= 0):
            raise ContractValidationError(
                f"{name}.{field_name}: must be positive integer"
            )

    for field_name in ("diverged", "qualified", "human_review_required"):
        if field_name in payload and not isinstance(
            payload[field_name], bool
        ):
            raise ContractValidationError(
                f"{name}.{field_name}: must be bool"
            )

    if name == "PromotionQualificationContract":
        status = payload.get("machine_status")
        if status in FORBIDDEN_PROMOTION_STATUSES:
            raise ContractValidationError(
                f"forbidden promotion status: {status}"
            )

    # Canonical ordering for deterministic dict/JSON output.
    normalized: dict[str, Any] = {}
    for key in _allowed_keys(name):
        if key in payload:
            normalized[key] = payload[key]
    return normalized


def serialize_contract(data: Mapping[str, Any]) -> str:
    """Deterministic UTF-8 JSON serialization (sorted keys, fixed separators)."""
    normalized = validate_contract_dict(data)
    text = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return text


def contract_sha256(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def deserialize_contract(text: str) -> dict[str, Any]:
    """Parse and validate serialized contract text (side-effect free)."""
    try:
        data = json.loads(text, parse_constant=_reject_nan)
    except (ValueError, TypeError) as exc:
        raise ContractValidationError(f"unparsable contract JSON: {exc}") \
            from exc
    return validate_contract_dict(data)


def roundtrip(data: Mapping[str, Any]) -> dict[str, Any]:
    return deserialize_contract(serialize_contract(data))


# ---------------------------------------------------------------------------
# Declarative dataclass shapes (documentation + typed construction).
# The canonical runtime carrier is the validated dict produced above.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ShadowRunContract:
    """Shadow computation identity record (P5-B01). No execution methods."""

    shadow_run_id: str
    decision_id: str
    source_snapshot_id: str
    evidence_pack_id: str
    canonical_baseline_id: str
    shadow_version_id: str
    evaluation_timestamp: str
    as_of_timestamp: str
    runtime_mode: str
    config_hash: str
    code_identity: str


@dataclass(frozen=True)
class DivergenceContract:
    canonical_decision_id: str
    shadow_decision_id: str
    diverged: bool
    severity: str
    explanation: str
    review_state: str
    reason_code: str | None = None
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class OutcomeContract:
    decision_id: str
    as_of_timestamp: str
    observation_timestamp: str
    horizon: int
    outcome_status: str
    future_return: float | None = None
    mae: float | None = None
    mfe: float | None = None
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class AgingContract:
    evidence_id: str
    observed_at: str
    evaluated_at: str
    policy_version: str
    aging_state: str
    reason: str
    age: float | None = None


@dataclass(frozen=True)
class IncidentContract:
    incident_id: str
    incident_type: str
    severity: str
    status: str
    detected_at: str
    human_review_required: bool
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    affected_decisions: tuple[str, ...] = field(default_factory=tuple)
    replay_refs: tuple[str, ...] = field(default_factory=tuple)
    resolution: str | None = None


@dataclass(frozen=True)
class PromotionQualificationContract:
    candidate_id: str
    qualified: bool
    machine_status: str
    evaluated_at: str
    gate_results: dict[str, bool] = field(default_factory=dict)
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    blocking_gates: tuple[str, ...] = field(default_factory=tuple)


def contract_dict(instance: Any) -> dict[str, Any]:
    """Convert a declarative contract dataclass to its validated carrier."""
    from dataclasses import asdict

    name = type(instance).__name__
    payload = asdict(instance)
    # Tuples must become lists for JSON determinism.
    payload = json.loads(json.dumps(payload, ensure_ascii=False))
    payload["schema_name"] = name
    payload["schema_version"] = schema_version(name)
    return validate_contract_dict(payload)
