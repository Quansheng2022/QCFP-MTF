# coding: utf-8
"""P5-C / WP5.1 — independent Shadow storage.

Shadow evidence is written ONLY under an explicitly configured storage root.
No canonical ledger / tactical / permission / FSM / execution state is ever
touched by this module.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .contracts import validate_contract_dict
from .shadow_runtime import (
    ShadowRuntimeError,
    deterministic_dumps,
    sha256_payload,
)


SHADOW_DECISION_SCHEMA = "PHASE5-SHADOW-DECISION-1"
CANONICAL_STORE_DIR_NAMES = ("SQLiteDB",)


class ShadowStore:
    """File-backed shadow store with deterministic serialization."""

    @staticmethod
    def _write_once_or_verify_identical(path: Path, text: str) -> None:
        """CREATE once; identical rewrite is a no-op; divergent rewrite fails."""
        encoded = text.encode("utf-8")
        if path.exists():
            if path.read_bytes() != encoded:
                raise ShadowRuntimeError(
                    f"SHADOW_RUN_IMMUTABILITY_VIOLATION: {path}"
                )
            return
        path.write_bytes(encoded)

    def __init__(self, root: Path):
        if root is None:
            raise ShadowRuntimeError(
                "shadow storage root must be explicit; refusing default "
                "canonical storage"
            )
        root = Path(root)
        resolved = root.resolve()
        if any(
            part in CANONICAL_STORE_DIR_NAMES for part in resolved.parts
        ):
            raise ShadowRuntimeError(
                f"shadow store root must not live inside canonical storage "
                f"(contains {CANONICAL_STORE_DIR_NAMES}): {resolved}"
            )
        self._root = root
        self._runs = root / "runs"
        self._decisions = root / "decisions"

    @property
    def root(self) -> Path:
        return self._root

    def write(
        self,
        *,
        identity: Mapping[str, Any],
        decision_output: Mapping[str, Any],
        input_payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        validated = validate_contract_dict(identity)
        run_id = validated["shadow_run_id"]
        self._runs.mkdir(parents=True, exist_ok=True)
        self._decisions.mkdir(parents=True, exist_ok=True)

        run_path = self._runs / f"{run_id}.json"
        self._write_once_or_verify_identical(
            run_path, deterministic_dumps(validated))

        input_sha = sha256_payload(input_payload)
        output_sha = sha256_payload(decision_output)
        decision = {
            "schema": SHADOW_DECISION_SCHEMA,
            "shadow_run_id": run_id,
            "input_sha256": input_sha,
            "output_sha256": output_sha,
            "input": dict(input_payload),
            "output": dict(decision_output),
        }
        decision_path = self._decisions / f"{run_id}.json"
        self._write_once_or_verify_identical(
            decision_path, deterministic_dumps(decision))
        return {
            "run_id": run_id,
            "run_path": str(run_path),
            "decision_path": str(decision_path),
            "input_sha256": input_sha,
            "output_sha256": output_sha,
        }

    def read(self, run_id: str) -> dict[str, Any]:
        path = self._runs / f"{run_id}.json"
        if not path.exists():
            raise ShadowRuntimeError(f"shadow run not found: {run_id}")
        return validate_contract_dict(json.loads(
            path.read_text(encoding="utf-8")))

    def read_decision(self, run_id: str) -> dict[str, Any]:
        path = self._decisions / f"{run_id}.json"
        if not path.exists():
            raise ShadowRuntimeError(
                f"shadow decision record not found: {run_id}"
            )
        return json.loads(path.read_text(encoding="utf-8"))

    def list_runs(self) -> list[str]:
        if not self._runs.exists():
            return []
        return sorted(p.stem for p in self._runs.glob("*.json"))
