# coding: utf-8
"""P5-C / WP5.1 — governed Shadow Runtime (contract layer consumers).

This module implements the *runtime* promised by P5-B Contract v1 without
modifying those contracts:

    * shadow run identity (deterministic, contract-validated)
    * CANONICAL / SHADOW / REPLAY runtime modes (fail closed)
    * canonical evaluation bridge (READ/CALL only; never writes back)
    * independent Shadow storage + replay (see shadow_store / shadow_replay)
    * deterministic, auditable runtime evidence

Boundaries kept for later work packages:
    * P5-D: systematic isolation proof / adversarial matrix (not here)
    * P5-E: divergence taxonomy/classifier (not here)
    * P5-F..P5-I: outcome / aging / incident / promotion (not here)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from .contracts import (
    ContractValidationError,
    RUNTIME_MODES,
    validate_contract_dict,
)


class ShadowRuntimeError(RuntimeError):
    """Fail-closed runtime error."""


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def deterministic_dumps(payload: Mapping[str, Any]) -> str:
    """Deterministic JSON text (sorted keys, fixed separators, UTF-8)."""
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_payload(payload: Mapping[str, Any]) -> str:
    return sha256_text(deterministic_dumps(payload))


def validate_runtime_mode(mode: str) -> str:
    """Runtime mode fail-closed guard (EXECUTE/PRODUCTION/AUTO rejected)."""
    if mode not in RUNTIME_MODES:
        raise ShadowRuntimeError(
            f"invalid runtime_mode {mode!r}; allowed: {RUNTIME_MODES}"
        )
    return mode


class ShadowIdentityFactory:
    """Deterministic identity builder consumed by P5-B ShadowRunContract."""

    IDENTITY_FIELDS = (
        "decision_id",
        "source_snapshot_id",
        "evidence_pack_id",
        "canonical_baseline_id",
        "shadow_version_id",
        "config_hash",
        "code_identity",
        "as_of_timestamp",
        "runtime_mode",
    )

    def generate(
        self,
        *,
        decision_id: str,
        source_snapshot_id: str,
        evidence_pack_id: str,
        canonical_baseline_id: str,
        shadow_version_id: str,
        config_hash: str,
        code_identity: str,
        as_of_timestamp: str,
        runtime_mode: str = "SHADOW",
        evaluation_timestamp: str | None = None,
    ) -> dict[str, Any]:
        """Build a validated ShadowRunContract carrier dict.

        The shadow_run_id is the SHA256 of the canonical identity fields, so
        identical identity inputs produce an identical id (replay-traceable).
        """
        validate_runtime_mode(runtime_mode)
        identity_seed = {
            key: locals()[key]
            for key in self.IDENTITY_FIELDS
        }
        seed_text = deterministic_dumps(identity_seed)
        shadow_run_id = sha256_text(seed_text)
        carrier = {
            "schema_name": "ShadowRunContract",
            "schema_version": 1,
            "shadow_run_id": shadow_run_id,
            **identity_seed,
            "evaluation_timestamp": evaluation_timestamp or now_utc(),
        }
        return validate_contract_dict(carrier)


def canonical_evaluate(
    evidence: Mapping[str, Any],
    previous_state: str,
    previous_position: float,
    settings: Mapping[str, Any],
    config: Any = None,
    rule_version: str | None = None,
    model_version: str | None = None,
    run_id: str = "",
    decision_id: str | None = None,
) -> dict[str, Any]:
    """Read/call bridge to the frozen canonical evaluation authority.

    Shadow Runtime never re-implements canonical decision logic; it only calls
    the approved surface and records the returned snapshot as shadow evidence.
    """
    from QCFP_MTF.decision.engine import evaluate  # read-only call

    snapshot = evaluate(
        dict(evidence),
        previous_state,
        previous_position,
        settings,
        config=config,
        rule_version=rule_version,
        model_version=model_version,
        run_id=run_id,
        decision_id=decision_id,
    )
    return asdict(snapshot)


Evaluator = Callable[..., Mapping[str, Any]]


class ShadowRuntime:
    """Executes a governed shadow computation into independent storage."""

    def __init__(self, store: Any, evaluator: Evaluator | None = None):
        self._store = store
        self._identity = ShadowIdentityFactory()
        self._evaluator = evaluator

    def execute(
        self,
        *,
        mode: str,
        input_payload: Mapping[str, Any],
        decision_id: str,
        source_snapshot_id: str,
        evidence_pack_id: str,
        canonical_baseline_id: str,
        shadow_version_id: str,
        config_hash: str,
        code_identity: str,
        as_of_timestamp: str,
        evaluation_timestamp: str | None = None,
        evaluator: Evaluator | None = None,
    ) -> dict[str, Any]:
        """Record a Shadow/Replay evaluation without touching canonical state.

        Generic execution is SHADOW-only. CANONICAL and REPLAY each have a
        dedicated governed entry point (capture_canonical / replay_shadow_run)
        and must not be reachable through this generic surface.
        """
        validate_runtime_mode(mode)
        if mode != "SHADOW":
            if mode == "CANONICAL":
                raise ShadowRuntimeError(
                    "CANONICAL mode requires ShadowRuntime.capture_canonical()"
                )
            if mode == "REPLAY":
                raise ShadowRuntimeError(
                    "REPLAY mode requires replay_shadow_run()"
                )
            raise ShadowRuntimeError(
                f"unsupported generic runtime mode: {mode}"
            )
        fn = evaluator or self._evaluator
        if fn is None:
            raise ShadowRuntimeError(
                "no evaluator provided; shadow run cannot execute"
            )
        identity = self._identity.generate(
            decision_id=decision_id,
            source_snapshot_id=source_snapshot_id,
            evidence_pack_id=evidence_pack_id,
            canonical_baseline_id=canonical_baseline_id,
            shadow_version_id=shadow_version_id,
            config_hash=config_hash,
            code_identity=code_identity,
            as_of_timestamp=as_of_timestamp,
            runtime_mode=mode,
            evaluation_timestamp=evaluation_timestamp,
        )
        decision_output = dict(fn(input_payload))
        meta = self._store.write(
            identity=identity,
            decision_output=decision_output,
            input_payload=dict(input_payload),
        )
        return {
            "shadow_run_id": identity["shadow_run_id"],
            "runtime_mode": mode,
            "store_root": str(self._store.root),
            "input_sha256": meta["input_sha256"],
            "output_sha256": meta["output_sha256"],
        }

    def capture_canonical(
        self,
        *,
        evidence: Mapping[str, Any],
        previous_state: str,
        previous_position: float,
        settings: Mapping[str, Any],
        decision_id: str,
        source_snapshot_id: str,
        evidence_pack_id: str,
        canonical_baseline_id: str,
        shadow_version_id: str,
        config_hash: str,
        code_identity: str,
        as_of_timestamp: str,
        config: Any = None,
        rule_version: str | None = None,
        model_version: str | None = None,
        run_id: str = "",
        evaluation_timestamp: str | None = None,
    ) -> dict[str, Any]:
        """CANONICAL capture through the fixed canonical evaluation bridge.

        No caller-supplied bridge exists: the recorded inputs are exactly the
        arguments passed to canonical_evaluate() -> decision.engine.evaluate(),
        so stored provenance cannot diverge from the actual canonical call.
        """
        recorded_input = {
            "evidence": dict(evidence),
            "previous_state": previous_state,
            "previous_position": previous_position,
            "settings": dict(settings),
            "config": config,
            "rule_version": rule_version,
            "model_version": model_version,
            "run_id": run_id,
            "decision_id": decision_id,
        }
        try:
            deterministic_dumps(recorded_input)
        except (TypeError, ValueError) as exc:
            raise ShadowRuntimeError(
                "canonical capture inputs are not deterministic JSON "
                f"serializable: {exc}"
            ) from exc

        identity = self._identity.generate(
            decision_id=decision_id,
            source_snapshot_id=source_snapshot_id,
            evidence_pack_id=evidence_pack_id,
            canonical_baseline_id=canonical_baseline_id,
            shadow_version_id=shadow_version_id,
            config_hash=config_hash,
            code_identity=code_identity,
            as_of_timestamp=as_of_timestamp,
            runtime_mode="CANONICAL",
            evaluation_timestamp=evaluation_timestamp,
        )
        decision_output = canonical_evaluate(
            evidence=evidence,
            previous_state=previous_state,
            previous_position=previous_position,
            settings=settings,
            config=config,
            rule_version=rule_version,
            model_version=model_version,
            run_id=run_id,
            decision_id=decision_id,
        )
        meta = self._store.write(
            identity=identity,
            decision_output=decision_output,
            input_payload=recorded_input,
        )
        return {
            "shadow_run_id": identity["shadow_run_id"],
            "runtime_mode": "CANONICAL",
            "store_root": str(self._store.root),
            "input_sha256": meta["input_sha256"],
            "output_sha256": meta["output_sha256"],
        }
