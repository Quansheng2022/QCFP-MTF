# coding: utf-8
"""P5-D / WP5.1 — Shadow Isolation proof helpers (pure verification only).

This module is NOT a new authority and performs no mutation. It provides
hash/state snapshots, diffing, storage-boundary validation, and zero-call
assertions used by the P5-D isolation tests.

Claim scope: GOVERNED_PHASE5_RUNTIME_SURFACE. Arbitrary malicious Python /
OS-level code execution sandboxing is NOT claimed here (that belongs to a
process/isolation architecture, not P5-D).
"""

from __future__ import annotations

import hashlib
import ast
import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Mapping


class IsolationViolation(RuntimeError):
    """Raised when an isolation proof assertion fails."""


CANONICAL_DIR_NAMES = ("SQLiteDB",)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot_files(
    root: Path, rel_paths: Iterable[str]
) -> dict[str, dict[str, Any]]:
    """Snapshot existence + sha256 + size for canonical authority files."""
    root = Path(root)
    snap: dict[str, dict[str, Any]] = {}
    for rel in sorted(rel_paths):
        path = root / rel
        if path.is_file():
            snap[rel] = {
                "exists": True,
                "sha256": sha256_file(path),
                "size": path.stat().st_size,
            }
        else:
            snap[rel] = {"exists": False, "sha256": None, "size": None}
    return snap


def snapshot_canonical_db(db_path: Path) -> dict[str, Any]:
    """Read-only snapshot of the canonical SQLite ledger surface."""
    db_path = Path(db_path)
    base: dict[str, Any] = {
        "exists": db_path.exists(),
        "size": db_path.stat().st_size if db_path.exists() else None,
        "mtime_ns": (
            db_path.stat().st_mtime_ns if db_path.exists() else None
        ),
        "ledger_count": None,
        "ledger_max_id": None,
    }
    if not db_path.exists():
        return base
    try:
        conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro",
                               uri=True)
        try:
            row = conn.execute(
                "SELECT COUNT(*), COALESCE(MAX(id), 0) "
                "FROM qcfp_decision_ledger"
            ).fetchone()
            base["ledger_count"] = int(row[0])
            base["ledger_max_id"] = int(row[1])
        except sqlite3.Error:
            base["ledger_count"] = None
            base["ledger_max_id"] = None
        finally:
            conn.close()
    except sqlite3.Error:
        base["ledger_count"] = None
        base["ledger_max_id"] = None
    return base


def snapshot_sqlite_family(db_path: Path) -> dict[str, dict[str, Any]]:
    """Byte-level read-only snapshot of db + wal + shm (no write connection)."""
    db_path = Path(db_path)
    family: dict[str, dict[str, Any]] = {}
    for suffix in ("", "-wal", "-shm"):
        path = Path(f"{db_path}{suffix}")
        rel = f"{db_path.name}{suffix}"
        if path.exists() and path.is_file():
            family[rel] = {
                "exists": True,
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        else:
            family[rel] = {"exists": False, "size": None, "sha256": None}
    return family


def diff_snapshots(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> dict[str, list[str]]:
    modified = [
        key for key in set(before) & set(after)
        if before[key] != after[key]
    ]
    created = [key for key in after if key not in before]
    deleted = [key for key in before if key not in after]
    return {
        "modified": sorted(modified),
        "created": sorted(created),
        "deleted": sorted(deleted),
    }


def assert_authority_unchanged(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> None:
    diff = diff_snapshots(before, after)
    if any(diff.values()):
        raise IsolationViolation(
            "CANONICAL_MUTATION_DETECTED: "
            + json.dumps(diff, sort_keys=True)
        )


def assert_zero_calls(call_count: int, label: str) -> None:
    if call_count != 0:
        raise IsolationViolation(
            f"{label} call count = {call_count}; expected 0"
        )


def validate_shadow_storage_boundary(root: Path) -> dict[str, Any]:
    """Reject any shadow storage root that resolves inside canonical storage."""
    resolved = Path(root).resolve()
    hit = [part for part in resolved.parts
           if part in CANONICAL_DIR_NAMES]
    if hit:
        raise IsolationViolation(
            f"shadow storage resolves into canonical storage "
            f"(contains {hit}): {resolved}"
        )
    return {"path": str(resolved), "isolated": True}


FORBIDDEN_DIRECT_IMPORT_MODULES = (
    "QCFP_MTF.decision.decision_ledger",
    "QCFP_MTF.decision.governance",
    "QCFP_MTF.decision.governance_caps",
    "QCFP_MTF.decision.permission_gate",
    "QCFP_MTF.decision.permission_policy",
    "QCFP_MTF.decision.institutional_permission",
    "QCFP_MTF.decision.retail_fsm",
    "QCFP_MTF.decision.retail_position_fsm",
    "QCFP_MTF.decision.fsm_authority",
    "QCFP_MTF.governance.promotion_gate",
    "QCFP_MTF.governance.qualification_promotion",
    "QCFP_MTF.governance.runtime_promotion_gate",
    "QCFP_MTF.execution",
)


def assert_no_forbidden_imports(root: Path, py_files: Iterable[str]) -> None:
    """AST-based static boundary: Phase5 modules may only import the approved
    canonical engine bridge (QCFP_MTF.decision.engine), never direct
    Authority implementations / production modules."""
    violations: list[str] = []
    for rel in py_files:
        path = root / rel
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError) as exc:
            violations.append(f"{rel}: unparsable ({exc})")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                full = module
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    full = alias.name
                    if any(
                        full == forbidden
                        or full.startswith(forbidden + ".")
                        for forbidden in FORBIDDEN_DIRECT_IMPORT_MODULES
                    ):
                        violations.append(f"{rel}:{node.lineno}: {full}")
                continue
            else:
                continue
            if any(
                full == forbidden or full.startswith(forbidden + ".")
                for forbidden in FORBIDDEN_DIRECT_IMPORT_MODULES
            ):
                violations.append(f"{rel}:{node.lineno}: {full}")
    if violations:
        raise IsolationViolation(
            "FORBIDDEN_DIRECT_AUTHORITY_IMPORT: " + "; ".join(violations)
        )
