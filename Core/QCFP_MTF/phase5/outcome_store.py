# coding: utf-8
"""P5-F / WP5.3 — append-only Outcome Observation sidecar store.

Outcome evidence is written ONLY as an independent, append-only sidecar:

    * never ``UPDATE`` a Decision / Decision Ledger with outcome columns
    * never mutate an existing observation file (CREATE once or identical)
    * data revision appends a NEW observation version (``supersedes``),
      leaving the historical claim readable and hash-verifiable
    * every observation embeds the frozen P5-B ``OutcomeContract`` payload

The observation file schema is ``PHASE5-OUTCOME-OBSERVATION-1``.  The outer
record adds provenance / replay identity that the frozen P5-B contract does
not carry (market-data identity, price basis, policy/metric versions,
observation cutoff, decision hash); the embedded ``contract`` field is the
canonical P5-B OutcomeContract carrier and is validated unchanged.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from .contracts import validate_contract_dict
from .shadow_runtime import deterministic_dumps


class OutcomeStoreError(RuntimeError):
    """Fail-closed outcome store error."""


OBSERVATION_SCHEMA = "PHASE5-OUTCOME-OBSERVATION-1"

# Minimal P5-F observation lifecycle (P5-G/P5-H vocabulary is NOT used here).
OBSERVED_STATUSES = ("OBSERVED", "DATA_UNAVAILABLE", "OBSERVATION_ERROR")
DIRECTIONS = ("LONG", "SHORT", "FLAT", "NONE")
PRICE_BASES = ("ADJUSTED", "UNADJUSTED")
REFERENCE_SOURCES = ("DECISION", "MARKET_T0", "NONE")

# P5-B OutcomeContract status vocabulary is frozen; P5-F maps its observer
# status to the frozen contract status without inventing new contract values.
CONTRACT_STATUS_MAP = {
    "OBSERVED": "REALIZED",
    "DATA_UNAVAILABLE": "MISSING_DATA",
    "OBSERVATION_ERROR": "INVALID",
}

OBSERVATION_REQUIRED = (
    "schema", "observation_id", "decision_id", "instrument_id", "horizon",
    "outcome_status", "observation_timestamp", "observation_cutoff",
    "policy_version", "horizon_policy_version", "metric_version",
    "interpretation_policy_version", "direction_interpretation",
    "decision_hash", "market_data_source_identity",
    "market_data_snapshot_identity", "price_basis", "adjustment_policy",
    "source_version", "reference_price", "reference_price_source",
    "horizon_price", "path_high", "path_low", "raw_return",
    "raw_max_excursion", "raw_min_excursion", "future_return",
    "directional_mfe", "directional_mae", "contract", "evidence_hash",
)
OBSERVATION_OPTIONAL = ("supersedes", "reason", "reason_code")

IDENTITY_SEED_FIELDS = (
    "decision_id", "decision_hash", "instrument_id", "horizon",
    "horizon_policy_version", "metric_version",
    "interpretation_policy_version", "policy_version",
    "market_data_source_identity", "market_data_snapshot_identity",
    "observation_cutoff",
)

UTC_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
NUMBER_FIELDS = (
    "reference_price", "horizon_price", "path_high", "path_low",
    "raw_return", "raw_max_excursion", "raw_min_excursion",
    "future_return", "directional_mfe", "directional_mae",
)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_payload(payload: Mapping[str, Any]) -> str:
    return sha256_text(deterministic_dumps(payload))


def _valid_utc(value: Any) -> bool:
    if not isinstance(value, str) or not UTC_TS_RE.match(value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return True


def _finite(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        import math

        return math.isfinite(value)
    return False


def _allowed_keys() -> tuple[str, ...]:
    return OBSERVATION_REQUIRED + OBSERVATION_OPTIONAL


def observation_evidence_hash(
    record: Mapping[str, Any],
) -> str:
    """Deterministic SHA-256 over every observation field except evidence_hash."""
    payload = {key: value for key, value in record.items()
               if key != "evidence_hash"}
    return sha256_payload(payload)


def observation_identity_seed(record: Mapping[str, Any]) -> dict[str, Any]:
    missing = [key for key in IDENTITY_SEED_FIELDS
               if key not in record]
    if missing:
        raise OutcomeStoreError(
            f"observation identity seed incomplete (missing: {missing})"
        )
    return {key: record[key] for key in IDENTITY_SEED_FIELDS}


def observation_id_from_seed(seed: Mapping[str, Any]) -> str:
    return sha256_payload(seed)


def validate_observation(record: Mapping[str, Any]) -> dict[str, Any]:
    """Fail-closed validation + canonicalization of an observation record."""
    if not isinstance(record, Mapping):
        raise OutcomeStoreError("observation record must be a mapping")
    payload = dict(record)
    if payload.get("schema") != OBSERVATION_SCHEMA:
        raise OutcomeStoreError(
            f"missing/unknown schema: {payload.get('schema')!r}"
        )
    unknown = sorted(set(payload) - set(_allowed_keys()))
    if unknown:
        raise OutcomeStoreError(
            f"{OBSERVATION_SCHEMA}: unknown field(s): {unknown}"
        )
    missing = [key for key in OBSERVATION_REQUIRED if key not in payload]
    if missing:
        raise OutcomeStoreError(
            f"{OBSERVATION_SCHEMA}: missing required field(s): {missing}"
        )
    for key in ("decision_id", "instrument_id", "decision_hash",
                "policy_version", "horizon_policy_version", "metric_version",
                "interpretation_policy_version",
                "market_data_source_identity",
                "market_data_snapshot_identity", "price_basis",
                "adjustment_policy", "source_version"):
        value = payload.get(key)
        if not isinstance(value, str) or value.strip() == "":
            raise OutcomeStoreError(
                f"{OBSERVATION_SCHEMA}.{key}: must be non-empty string"
            )
    if payload["outcome_status"] not in OBSERVED_STATUSES:
        raise OutcomeStoreError(
            f"{OBSERVATION_SCHEMA}.outcome_status: invalid "
            f"{payload['outcome_status']!r} (persisted statuses: "
            f"{sorted(OBSERVED_STATUSES)})"
        )
    horizon = payload["horizon"]
    if isinstance(horizon, bool) or not isinstance(horizon, int) \
            or horizon <= 0:
        raise OutcomeStoreError(
            f"{OBSERVATION_SCHEMA}.horizon: must be positive integer"
        )
    if payload["direction_interpretation"] not in DIRECTIONS:
        raise OutcomeStoreError(
            f"{OBSERVATION_SCHEMA}.direction_interpretation: invalid "
            f"{payload['direction_interpretation']!r}"
        )
    if payload["price_basis"] not in PRICE_BASES:
        raise OutcomeStoreError(
            f"{OBSERVATION_SCHEMA}.price_basis: invalid "
            f"{payload['price_basis']!r} (allowed: {sorted(PRICE_BASES)})"
        )
    if payload["reference_price_source"] not in REFERENCE_SOURCES:
        raise OutcomeStoreError(
            f"{OBSERVATION_SCHEMA}.reference_price_source: invalid "
            f"{payload['reference_price_source']!r}"
        )
    for key in ("observation_timestamp", "observation_cutoff"):
        if not _valid_utc(payload.get(key)):
            raise OutcomeStoreError(
                f"{OBSERVATION_SCHEMA}.{key}: invalid UTC timestamp "
                f"{payload.get(key)!r}"
            )
    if payload.get("supersedes") is not None \
            and not isinstance(payload["supersedes"], str):
        raise OutcomeStoreError(
            f"{OBSERVATION_SCHEMA}.supersedes: must be str or null"
        )
    if payload.get("reason") is not None \
            and not isinstance(payload["reason"], str):
        raise OutcomeStoreError(
            f"{OBSERVATION_SCHEMA}.reason: must be str or null"
        )
    if payload.get("reason_code") is not None \
            and not isinstance(payload["reason_code"], str):
        raise OutcomeStoreError(
            f"{OBSERVATION_SCHEMA}.reason_code: must be str or null"
        )
    if payload["outcome_status"] == "OBSERVED" \
            and (payload.get("reason") is not None
                 or payload.get("reason_code") is not None):
        raise OutcomeStoreError(
            "OBSERVED observation must not carry a reason/reason_code"
        )
    for key in NUMBER_FIELDS:
        value = payload.get(key)
        if value is not None and not _finite(value):
            raise OutcomeStoreError(
                f"{OBSERVATION_SCHEMA}.{key}: must be finite number or null, "
                f"got {value!r}"
            )

    # Frozen P5-B OutcomeContract must itself validate and agree.
    contract = payload.get("contract")
    if not isinstance(contract, Mapping):
        raise OutcomeStoreError(
            f"{OBSERVATION_SCHEMA}.contract: missing embedded OutcomeContract"
        )
    try:
        contract = validate_contract_dict(contract)
    except Exception as exc:
        raise OutcomeStoreError(
            f"embedded OutcomeContract invalid: {exc}"
        ) from exc
    if contract.get("schema_name") != "OutcomeContract":
        raise OutcomeStoreError(
            f"embedded contract must be OutcomeContract, got "
            f"{contract.get('schema_name')!r}"
        )
    expected_contract_status = CONTRACT_STATUS_MAP.get(
        payload["outcome_status"])
    if expected_contract_status is None \
            or contract.get("outcome_status") != expected_contract_status:
        raise OutcomeStoreError(
            "contract outcome_status mismatch: "
            f"observer={payload['outcome_status']!r} "
            f"contract={contract.get('outcome_status')!r} "
            f"(expected {expected_contract_status!r})"
        )
    cross = [
        ("decision_id", payload["decision_id"], contract.get("decision_id")),
        ("horizon", payload["horizon"], contract.get("horizon")),
    ]
    for key, outer_value, contract_value in cross:
        if outer_value != contract_value:
            raise OutcomeStoreError(
                f"{OBSERVATION_SCHEMA}.contract.{key} mismatch: "
                f"outer={outer_value!r} contract={contract_value!r}"
            )
    metric_pairs = (
        ("future_return", "future_return"),
        ("directional_mae", "mae"),
        ("directional_mfe", "mfe"),
    )
    for outer_key, contract_key in metric_pairs:
        outer_value = payload.get(outer_key)
        contract_value = contract.get(contract_key)
        if outer_value is None and contract_value is None:
            continue
        if outer_value is None or contract_value is None \
                or abs(float(outer_value) - float(contract_value)) > 1e-9:
            raise OutcomeStoreError(
                f"{OBSERVATION_SCHEMA}.contract.{contract_key} mismatch: "
                f"outer={outer_value!r} contract={contract_value!r}"
            )

    if payload["outcome_status"] == "OBSERVED":
        for key in ("reference_price", "horizon_price", "path_high",
                    "path_low", "raw_return", "raw_max_excursion",
                    "raw_min_excursion"):
            if payload.get(key) is None:
                raise OutcomeStoreError(
                    f"OBSERVED outcome missing raw metric {key}"
                )
        if payload["direction_interpretation"] in ("LONG", "SHORT"):
            for key in ("future_return", "directional_mae",
                        "directional_mfe"):
                if payload.get(key) is None:
                    raise OutcomeStoreError(
                        f"OBSERVED directional outcome missing {key}"
                    )
    else:
        for key in NUMBER_FIELDS:
            if payload.get(key) is not None:
                raise OutcomeStoreError(
                    f"{payload['outcome_status']} observation must carry "
                    f"null metric {key}, got {payload[key]!r}"
                )

    normalized = {key: payload.get(key) for key in _allowed_keys()}
    normalized["contract"] = contract
    normalized["evidence_hash"] = observation_evidence_hash(normalized)
    seed = observation_identity_seed(normalized)
    expected_id = observation_id_from_seed(seed)
    if normalized["observation_id"] != expected_id:
        raise OutcomeStoreError(
            "observation_id mismatch: "
            f"recorded={normalized['observation_id']!r} "
            f"expected={expected_id!r}"
        )
    if normalized["evidence_hash"] != payload.get("evidence_hash"):
        raise OutcomeStoreError("evidence_hash mismatch")
    return normalized


class OutcomeStore:
    """File-backed append-only Outcome Observation sidecar store."""

    CANONICAL_STORE_DIR_NAMES = ("SQLiteDB",)

    def __init__(self, root: Path):
        if root is None:
            raise OutcomeStoreError(
                "outcome storage root must be explicit; refusing default "
                "canonical storage"
            )
        root = Path(root)
        resolved = root.resolve()
        if any(
            part in self.CANONICAL_STORE_DIR_NAMES
            for part in resolved.parts
        ):
            raise OutcomeStoreError(
                f"outcome store root must not live inside canonical storage "
                f"(contains {self.CANONICAL_STORE_DIR_NAMES}): {resolved}"
            )
        self._root = resolved
        self._observations = resolved / "observations"

    @property
    def root(self) -> Path:
        return self._root

    @staticmethod
    def _semantic_payload(record: Mapping[str, Any]) -> str:
        """Observation semantics ignore wall-clock observation_timestamp."""
        payload = {key: value for key, value in record.items()
                   if key not in ("observation_timestamp", "evidence_hash")}
        contract = payload.get("contract")
        if isinstance(contract, Mapping):
            payload = dict(payload)
            payload["contract"] = {
                key: value for key, value in contract.items()
                if key != "observation_timestamp"
            }
        return deterministic_dumps(payload)

    def write(self, record: Mapping[str, Any]) -> dict[str, Any]:
        """Append once; identical semantic duplicate is a no-op."""
        validated = validate_observation(record)
        observation_id = validated["observation_id"]
        self._observations.mkdir(parents=True, exist_ok=True)
        path = self._observations / f"{observation_id}.json"
        text = deterministic_dumps(validated)
        encoded = text.encode("utf-8")
        if path.exists():
            existing = path.read_bytes()
            if existing == encoded:
                return {
                    "observation_id": observation_id,
                    "path": str(path),
                    "written": False,
                    "status": "DUPLICATE_IDENTICAL",
                }
            existing_record = json.loads(existing.decode("utf-8"))
            if self._semantic_payload(existing_record) \
                    == self._semantic_payload(validated):
                return {
                    "observation_id": observation_id,
                    "path": str(path),
                    "written": False,
                    "status": "DUPLICATE_SEMANTIC_NOOP",
                }
            raise OutcomeStoreError(
                f"OUTCOME_OBSERVATION_IMMUTABILITY_VIOLATION: {path}"
            )
        path.write_bytes(encoded)
        return {
            "observation_id": observation_id,
            "path": str(path),
            "written": True,
            "status": "CREATED",
        }

    def read(self, observation_id: str) -> dict[str, Any]:
        path = self._observations / f"{observation_id}.json"
        if not path.exists():
            raise OutcomeStoreError(
                f"outcome observation not found: {observation_id}"
            )
        return validate_observation(
            json.loads(path.read_text(encoding="utf-8")))

    def list_observations(self, decision_id: str | None = None) -> list[str]:
        if not self._observations.exists():
            return []
        result = []
        for path in self._observations.glob("*.json"):
            record = json.loads(path.read_text(encoding="utf-8"))
            if decision_id is None or record.get("decision_id") == decision_id:
                result.append(record["observation_id"])
        return sorted(result)
