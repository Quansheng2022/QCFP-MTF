# coding: utf-8
"""P5-C / WP5.1 — Shadow run replay from governed recorded inputs."""

from __future__ import annotations

from typing import Any, Mapping

from .shadow_runtime import (
    Evaluator,
    ShadowRuntimeError,
    sha256_payload,
)


class ReplayMismatch(ShadowRuntimeError):
    """Fail-closed mismatch during shadow replay."""


REPLAY_CHECK_FIELDS = (
    "source_snapshot_id",
    "canonical_baseline_id",
    "shadow_version_id",
    "config_hash",
    "code_identity",
    "as_of_timestamp",
)


def replay_shadow_run(
    store: Any,
    run_id: str,
    evaluator: Evaluator,
    *,
    expected: Mapping[str, str],
    evaluation_timestamp: str | None = None,
) -> dict[str, Any]:
    """Re-execute a recorded shadow run in REPLAY mode.

    Fails closed if the recorded identity does not match the expected governed
    inputs, if recorded source inputs are missing, or if recomputed output no
    longer hashes to the recorded output.
    """
    identity = store.read(run_id)
    decision = store.read_decision(run_id)
    recorded_input = decision.get("input")
    if not isinstance(recorded_input, Mapping):
        raise ReplayMismatch(f"recorded source inputs missing for {run_id}")

    expected = dict(expected)
    mismatches: list[str] = []
    missing = [
        field for field in REPLAY_CHECK_FIELDS if field not in expected
    ]
    if missing:
        raise ReplayMismatch(
            "replay expected identity incomplete (missing: "
            + ", ".join(missing) + ")"
        )
    for field in REPLAY_CHECK_FIELDS:
        expected_value = expected[field]
        if expected_value != identity.get(field):
            mismatches.append(
                f"{field}: expected={expected_value!r} "
                f"recorded={identity.get(field)!r}"
            )
    if mismatches:
        raise ReplayMismatch("replay identity mismatch: " + " | ".join(mismatches))

    actual_input_sha = sha256_payload(recorded_input)
    if actual_input_sha != decision.get("input_sha256"):
        raise ReplayMismatch(
            f"recorded input hash mismatch for {run_id}: "
            f"actual={actual_input_sha} recorded={decision.get('input_sha256')}"
        )

    replay_identity = dict(identity)
    replay_identity["runtime_mode"] = "REPLAY"
    from .shadow_runtime import ShadowIdentityFactory

    replay_identity["shadow_run_id"] = ShadowIdentityFactory().generate(
        decision_id=identity["decision_id"],
        source_snapshot_id=identity["source_snapshot_id"],
        evidence_pack_id=identity["evidence_pack_id"],
        canonical_baseline_id=identity["canonical_baseline_id"],
        shadow_version_id=identity["shadow_version_id"],
        config_hash=identity["config_hash"],
        code_identity=identity["code_identity"],
        as_of_timestamp=identity["as_of_timestamp"],
        runtime_mode="REPLAY",
        evaluation_timestamp=evaluation_timestamp,
    )["shadow_run_id"]

    output = dict(evaluator(recorded_input))
    recomputed_sha = sha256_payload(output)
    if recomputed_sha != decision.get("output_sha256"):
        raise ReplayMismatch(
            f"replay output mismatch for {run_id}: "
            f"actual={recomputed_sha} recorded={decision.get('output_sha256')}"
        )

    meta = store.write(
        identity=replay_identity,
        decision_output=output,
        input_payload=recorded_input,
    )
    return {
        "original_shadow_run_id": run_id,
        "replay_shadow_run_id": meta["run_id"],
        "runtime_mode": "REPLAY",
        "replay_result": "MATCH",
    }
