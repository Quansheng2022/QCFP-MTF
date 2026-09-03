#!/usr/bin/env python3
"""
QCFP-MTF Phase 4 Development / Validation review bundle builder.

Version 4 (P1-REV-01 Closure):
    Changed-File Coverage Gate (P4-REVIEW-COVERAGE-01)
    Changed Target Text Files ⊆ Merged Review Files

The version-3 file-selection heuristic (path-keyword relevance) no longer
filters Git-changed files: any changed/untracked text file under
--target-root is merged unconditionally, so a Reviewer always sees the full
content of files a Candidate actually changed.

Purpose
-------
Create a deterministic, review-oriented merged text bundle for Phase 4:
Backtest / Ablation / OOS / Robustness / Cost / Regime /
Retail Practicality / Failure Analysis / Evidence / Acceptance.

Design principles
-----------------
1. Phase 4 validates the frozen Phase 3 Canonical Decision Chain.
2. Existing Phase 3 authority surfaces should not be silently modified.
3. Review bundles bind source identity, Git state, file hashes, validation
   findings, optional pytest output, and review-worthy source/evidence text.
4. Static checks are guardrails, not proof. Human/AI review remains required.
5. Unknown or ambiguous situations are surfaced rather than silently ignored.

Typical usage
-------------
python tools/review/merge_project_for_phase4_review.py --run-pytest

python tools/review/merge_project_for_phase4_review.py \
    --target-root Core/QCFP_MTF \
    --run-pytest

python tools/review/merge_project_for_phase4_review.py \
    --mode acceptance \
    --run-pytest \
    --pytest-scope full

python tools/review/merge_project_for_phase4_review.py \
    --project-root C:\\path\\to\\QCFP_MTF \
    --baseline cdcab0c
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence


TOOL_VERSION = "1.3.0"
DEFAULT_BASELINE = "cdcab0c"

TEXT_EXTENSIONS = {
    ".py", ".pyi", ".md", ".rst", ".txt",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".sql", ".csv",
}

# Never merge virtualenvs, caches, VCS internals or generated review bundles.
EXCLUDED_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".nox",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "dist",
    "build",
    "htmlcov",
    "Merged_Code",
}

EXCLUDED_FILE_GLOBS = (
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "*.so",
    "*.dll",
    "*.dylib",
    "*.exe",
    "*.zip",
    "*.tar",
    "*.gz",
    "*.7z",
    "*.parquet",
    "*.feather",
    "*.xlsx",
    "*.xls",
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.webp",
    "*.pdf",
)

# These are semantic hints, not a hard-coded repository schema.
PHASE4_PATH_HINTS = (
    "backtest/",
    "validation/",
    "tests/phase4/",
    "test_phase4",
    "phase4_",
    "phase4/",
    "evidence/phase4",
    "phase4/evidence",
    "ablation",
    "walk_forward",
    "walk-forward",
    "/oos",
    "robustness",
    "regime",
    "practicality",
    "failure",
)

# Existing files matching these patterns are treated as frozen Phase 3 authority
# surfaces when changed after the frozen baseline. Keep patterns conservative.
PROTECTED_PHASE3_AUTHORITY_PATTERNS = (
    "**/decision/engine.py",
    "**/decision_engine.py",
    "**/permission.py",
    "**/permission/**",
    "**/fsm.py",
    "**/fsm/**",
    "**/wave.py",
    "**/wave/**",
    "**/finalize_target.py",
    "**/ledger.py",
    "**/replay.py",
)

REVIEW_ANCHOR_PATTERNS = (
    "pyproject.toml",
    "pytest.ini",
    "setup.cfg",
    "tox.ini",
    "requirements*.txt",
    "**/*phase4*.md",
    "**/*phase_4*.md",
    "**/*phase4*.yaml",
    "**/*phase4*.yml",
    "**/*phase4*.json",
    "**/decision/engine.py",
    "**/decision_engine.py",
    "**/tests/phase4/**/*.py",
    "**/tests/**/test_*phase4*.py",
    "**/backtest/**/*.py",
    "**/validation/**/*.py",
    "**/evidence/**/*phase4*.py",
    "**/governance/**/*phase4*.py",
)

ACCEPTANCE_EVIDENCE_NAMES = (
    "phase4_acceptance.json",
    "phase4_acceptance.md",
    "phase4_acceptance_case_results.json",
    "phase4_regression_summary.json",
    "phase4_freeze_record.txt",
    "phase4_human_approval.txt",
    "evidence_manifest.json",
    "observed_diff.json",
    "change_impact.json",
    "implementation_contract_result.json",
    "acceptance_result.json",
    "scope_audit.json",
    "review_report.json",
    "review_resolution.json",
    "evidence_pack_readonly.json",
    "evidence_manifest_verification.json",
    "spec_conformance.json",
    "baseline.json",
    "traceability.json",
    "fgc_bypass_suite.json",
)


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    path: str
    message: str

    def render(self) -> str:
        where = f" [{self.path}]" if self.path else ""
        return f"{self.severity:<7} {self.code}{where}: {self.message}"


@dataclass(frozen=True)
class GitChange:
    status: str
    path: str
    old_path: str | None = None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build a Phase 4 development/validation review bundle."
    )
    p.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help=(
            "Git/pytest project root. Default: auto-detect from script/current directory. "
            "For TA_Workflow this should normally be the TA_Workflow repository root."
        ),
    )
    p.add_argument(
        "--target-root",
        type=Path,
        default=None,
        help=(
            "Source subtree to review. Relative paths are resolved under --project-root. "
            "Default: auto-detect Core/QCFP_MTF when present, otherwise project root."
        ),
    )
    p.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Merged output file. Default: "
            "<project>/Merged_Code/merged_phase4_<mode>_review.txt"
        ),
    )
    p.add_argument(
        "--mode",
        choices=("development", "acceptance"),
        default="development",
        help="development = work-in-progress review; acceptance = stricter evidence checks.",
    )
    p.add_argument(
        "--baseline",
        default=DEFAULT_BASELINE,
        help=f"Frozen Phase 3 Git baseline/tag/commit. Default: {DEFAULT_BASELINE}",
    )
    p.add_argument(
        "--scope",
        choices=("phase4", "changed", "all"),
        default="phase4",
        help=(
            "phase4 = Phase4-relevant files + authority anchors + changed protected "
            "Phase3 surfaces + ALL changed target text files (unconditional, "
            "P4-REVIEW-COVERAGE-01); changed = all Git-changed files + anchors; "
            "all = all eligible text files."
        ),
    )
    p.add_argument(
        "--run-pytest",
        action="store_true",
        help="Run pytest and embed the result in the review bundle.",
    )
    p.add_argument(
        "--pytest-scope",
        choices=("phase4", "targeted", "full"),
        default="targeted",
        help=(
            "phase4 = Phase4 tests only; targeted = Phase4 plus decision/governance "
            "tests when discoverable; full = entire pytest suite."
        ),
    )
    p.add_argument(
        "--pytest-extra-arg",
        action="append",
        default=[],
        help="Additional argument passed to pytest. May be specified multiple times.",
    )
    p.add_argument(
        "--no-pytest-fallback",
        action="store_true",
        help=(
            "Do not fall back to the full pytest suite when Phase 4/targeted "
            "test auto-discovery finds no explicit targets."
        ),
    )
    p.add_argument(
        "--skip-structure-validation",
        action="store_true",
        help="Skip Phase 4 structure/capability checks.",
    )
    p.add_argument(
        "--skip-static-boundary-validation",
        action="store_true",
        help="Skip heuristic source-boundary/PIT/OOS checks.",
    )
    p.add_argument(
        "--max-file-bytes",
        type=int,
        default=1_500_000,
        help="Maximum text file size to merge. Default: 1,500,000 bytes.",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero for ERROR/BLOCKER findings even without pytest failure.",
    )
    p.add_argument(
        "--no-line-numbers",
        action="store_true",
        help="Do not prefix merged source lines with line numbers.",
    )
    return p.parse_args()


def run(
    cmd: Sequence[str],
    cwd: Path,
    timeout: int = 1800,
) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            list(cmd),
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        return proc.returncode, proc.stdout.rstrip()
    except FileNotFoundError as exc:
        return 127, f"{type(exc).__name__}: {exc}"
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout or ""
        if isinstance(out, bytes):
            out = out.decode("utf-8", "replace")
        return 124, f"TIMEOUT after {timeout}s\n{out}".rstrip()


def looks_like_project_root(path: Path) -> bool:
    markers = (
        ".git",
        "pyproject.toml",
        "pytest.ini",
        "setup.cfg",
        "src",
        "tests",
    )
    score = sum((path / m).exists() for m in markers)
    return score >= 2


def discover_project_root(explicit: Path | None) -> Path:
    if explicit:
        root = explicit.expanduser().resolve()
        if not root.exists():
            raise SystemExit(f"ERROR: project root does not exist: {root}")
        return root

    starts = [Path.cwd().resolve(), Path(__file__).resolve().parent]
    seen: set[Path] = set()
    for start in starts:
        for candidate in (start, *start.parents):
            if candidate in seen:
                continue
            seen.add(candidate)
            if looks_like_project_root(candidate):
                return candidate

    return Path.cwd().resolve()


def resolve_target_root(project_root: Path, explicit: Path | None) -> Path:
    """Resolve the Phase 4 review target independently from the Git/pytest root."""
    if explicit is not None:
        candidate = explicit.expanduser()
        if not candidate.is_absolute():
            candidate = project_root / candidate
        candidate = candidate.resolve()
    else:
        preferred = (project_root / "Core" / "QCFP_MTF").resolve()
        candidate = preferred if preferred.exists() else project_root.resolve()

    if not candidate.exists():
        raise SystemExit(f"ERROR: target root does not exist: {candidate}")
    if not candidate.is_dir():
        raise SystemExit(f"ERROR: target root is not a directory: {candidate}")

    try:
        candidate.relative_to(project_root.resolve())
    except ValueError:
        raise SystemExit(
            "ERROR: target root must be inside project root so Git/source identity "
            f"can be bound consistently. project={project_root} target={candidate}"
        )
    return candidate


def relpath(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_text(path: Path) -> str:
    data = path.read_bytes()
    if b"\x00" in data:
        raise UnicodeError("NUL byte detected; likely binary")
    return data.decode("utf-8", errors="replace")


def is_excluded_dir(path: Path) -> bool:
    return any(part in EXCLUDED_DIR_NAMES for part in path.parts)


def is_excluded_file(path: Path) -> bool:
    name = path.name
    return any(fnmatch.fnmatch(name, pat) for pat in EXCLUDED_FILE_GLOBS)


def eligible_text_file(path: Path, max_file_bytes: int) -> bool:
    if not path.is_file():
        return False
    if is_excluded_dir(path):
        return False
    if is_excluded_file(path):
        return False
    if path.suffix.lower() not in TEXT_EXTENSIONS and path.name not in {
        "Dockerfile", "Makefile"
    }:
        return False
    try:
        if path.stat().st_size > max_file_bytes:
            return False
    except OSError:
        return False
    return True


def path_matches(rel: str, patterns: Iterable[str]) -> bool:
    rel = rel.replace("\\", "/")
    return any(
        fnmatch.fnmatch(rel, pat)
        or fnmatch.fnmatch("/" + rel, pat)
        or fnmatch.fnmatch(rel.lower(), pat.lower())
        for pat in patterns
    )


def phase4_relevant(rel: str) -> bool:
    low = "/" + rel.lower().replace("\\", "/")
    return any(h.lower() in low for h in PHASE4_PATH_HINTS)


def git_available(root: Path) -> bool:
    rc, _ = run(["git", "rev-parse", "--is-inside-work-tree"], root, timeout=30)
    return rc == 0


def git_text(root: Path, *args: str) -> str:
    rc, out = run(["git", *args], root, timeout=120)
    if rc != 0:
        return f"<git command failed rc={rc}: git {' '.join(args)}>\n{out}"
    return out


def git_commit_exists(root: Path, ref: str) -> bool:
    rc, _ = run(["git", "cat-file", "-e", f"{ref}^{{commit}}"], root, timeout=30)
    return rc == 0


def git_is_ancestor(root: Path, ancestor: str, descendant: str = "HEAD") -> bool:
    rc, _ = run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        root,
        timeout=30,
    )
    return rc == 0


def git_file_existed_at(root: Path, baseline: str, rel: str) -> bool:
    rc, _ = run(["git", "cat-file", "-e", f"{baseline}:{rel}"], root, timeout=30)
    return rc == 0


def parse_git_changes(root: Path, baseline: str) -> list[GitChange]:
    if not git_available(root) or not git_commit_exists(root, baseline):
        return []

    # Compare the frozen baseline directly to the CURRENT working tree.
    # This includes committed, staged and unstaged tracked changes. Untracked
    # files are handled separately by current_untracked_files().
    rc, out = run(
        ["git", "diff", "--name-status", "--find-renames", baseline, "--"],
        root,
        timeout=120,
    )
    if rc != 0:
        return []

    changes: list[GitChange] = []
    for raw in out.splitlines():
        if not raw.strip():
            continue
        cols = raw.split("\t")
        status = cols[0]
        if status.startswith(("R", "C")) and len(cols) >= 3:
            changes.append(GitChange(status=status, old_path=cols[1], path=cols[2]))
        elif len(cols) >= 2:
            changes.append(GitChange(status=status, path=cols[1]))
    return changes


def current_untracked_files(root: Path) -> list[str]:
    if not git_available(root):
        return []
    rc, out = run(["git", "status", "--porcelain", "--untracked-files=all"], root, timeout=60)
    if rc != 0:
        return []
    result = []
    for line in out.splitlines():
        if line.startswith("?? "):
            result.append(line[3:].strip().replace("\\", "/"))
    return result


def iter_all_eligible(root: Path, max_file_bytes: int) -> Iterable[Path]:
    for path in root.rglob("*"):
        if eligible_text_file(path, max_file_bytes):
            yield path


def collect_review_files(
    project_root: Path,
    target_root: Path,
    baseline: str,
    scope: str,
    max_file_bytes: int,
) -> list[Path]:
    """Select review files from the target subtree while preserving repo identity.

    project_root is the Git/pytest root. target_root is the QCFP-MTF subtree.

    phase4:
      * Phase4-relevant files under target_root
      * review anchors under target_root
      * changed frozen Phase3 authority files under target_root
      * project-level pytest/config anchors needed to interpret the test environment

    changed:
      * Git-changed/untracked eligible text files only when they are under target_root
      * plus project-level test/config anchors

    all:
      * every eligible text file under target_root
      * plus project-level test/config anchors
    """
    target_files = list(iter_all_eligible(target_root, max_file_bytes))
    by_repo_rel = {relpath(p, project_root): p for p in target_files}

    # Keep a very small set of repository-level files needed to understand pytest/build config.
    project_anchor_names = {
        "pyproject.toml", "pytest.ini", "setup.cfg", "tox.ini", "requirements.txt",
        "requirements-dev.txt", "requirements-test.txt",
    }
    project_anchors: set[Path] = set()
    for name in project_anchor_names:
        p = project_root / name
        if eligible_text_file(p, max_file_bytes):
            project_anchors.add(p)

    if scope == "all":
        selected = set(target_files) | project_anchors
        return sorted(selected, key=lambda p: relpath(p, project_root).lower())

    changes = parse_git_changes(project_root, baseline)
    changed_rels = {
        c.path.replace("\\", "/")
        for c in changes
        if c.status and c.status[0] != "D"
    }
    changed_rels.update(current_untracked_files(project_root))

    selected: set[Path] = set(project_anchors)

    for rel, path in by_repo_rel.items():
        target_rel = relpath(path, target_root)
        is_anchor = path_matches(target_rel, REVIEW_ANCHOR_PATTERNS)
        is_phase4 = phase4_relevant(target_rel)
        is_protected = path_matches(target_rel, PROTECTED_PHASE3_AUTHORITY_PATTERNS)
        is_changed = rel in changed_rels

        if is_anchor:
            selected.add(path)

        if scope == "changed":
            if is_changed:
                selected.add(path)
            continue

        # scope == phase4
        if is_phase4:
            selected.add(path)
        # P1-REV-01: changed target files are included unconditionally.
        # Path relevance (phase4/anchor/protected) can only ADD files, never
        # remove a file that the Candidate actually changed.
        if is_changed:
            selected.add(path)

    return sorted(selected, key=lambda p: relpath(p, project_root).lower())


def changed_target_records(
    project_root: Path,
    target_root: Path,
    changes: Sequence[GitChange],
    untracked_rels: Sequence[str],
    merged_rels: set[str],
    max_file_bytes: int,
) -> dict:
    """Classify every changed file under target_root for coverage accounting.

    Kind semantics:
        text_merged   eligible text file present in the merged bundle
        text_missing  eligible text file NOT in the merged bundle
        binary        changed binary file (INFO + 2A index, not merged)
        oversized     changed text file above max_file_bytes
    Files outside target_root are not forced (scope boundary).
    """
    target_rel = relpath(target_root, project_root).rstrip("/")
    rels = {
        c.path.replace("\\", "/")
        for c in changes
        if c.status and c.status[0] != "D"
    }
    rels.update(untracked_rels)
    rels = {r for r in rels if r}
    rows: list[dict] = []
    missing: list[str] = []
    binary: list[str] = []
    oversized: list[str] = []
    for rel in sorted(rels):
        norm = rel.replace("\\", "/")
        if not (norm == target_rel or norm.startswith(target_rel + "/")):
            continue
        path = project_root / norm
        merged = norm in merged_rels
        row: dict = {"rel": norm, "merged": merged}
        if not path.exists():
            continue
        suffix = path.suffix.lower()
        is_excluded = is_excluded_file(path)
        if suffix not in TEXT_EXTENSIONS or is_excluded:
            row["kind"] = "binary"
            row["sha256"] = None
            binary.append(norm)
        else:
            try:
                size = path.stat().st_size
            except OSError:
                size = -1
            if size > max_file_bytes:
                row["kind"] = "oversized"
                row["sha256"] = sha256_file(path)
                oversized.append(norm)
            else:
                row["kind"] = "text_merged" if merged else "text_missing"
                row["sha256"] = sha256_file(path)
                if not merged:
                    missing.append(norm)
        rows.append(row)
    text_count = len([r for r in rows if r.get("kind") in (
        "text_merged", "text_missing", "oversized")])
    merged_text_count = len([r for r in rows if r.get("kind")
                             == "text_merged"])
    return {
        "rows": rows,
        "changed_target_text_count": text_count,
        "merged_changed_target_text_count": merged_text_count,
        "missing_changed_target_files": missing,
        "excluded_binary_files": binary,
        "excluded_oversized_files": oversized,
        "rule": "Changed Target Text Files ⊆ Merged Review Files "
                "(P4-REVIEW-COVERAGE-01)",
    }


def coverage_findings(coverage: dict, mode: str) -> list[Finding]:
    """Translate coverage accounting into gate findings."""
    out: list[Finding] = []
    missing = coverage["missing_changed_target_files"]
    oversized = coverage["excluded_oversized_files"]
    for rel in missing:
        out.append(Finding(
            "ERROR" if mode != "acceptance" else "BLOCKER",
            "P4-REVIEW-COVERAGE-01",
            rel,
            "changed target text file was not merged",
        ))
    for rel in oversized:
        out.append(Finding(
            "WARN" if mode != "acceptance" else "ERROR",
            "P4-REVIEW-COVERAGE-01",
            rel,
            "changed target text file oversized (see 2A index)",
        ))
    for rel in coverage["excluded_binary_files"]:
        out.append(Finding(
            "INFO",
            "P4-REVIEW-COVERAGE-01",
            rel,
            "changed binary file excluded from text merge (see 2A index)",
        ))
    merged = coverage["merged_changed_target_text_count"]
    total = coverage["changed_target_text_count"]
    if not missing and not oversized:
        out.append(Finding(
            "PASS",
            "P4-REVIEW-COVERAGE-01",
            "",
            f"changed target text files merged: {merged}/{total}",
        ))
    return out


def render_coverage_section(coverage: dict, mode: str) -> str:
    """Render '2A. CHANGED-FILE REVIEW COVERAGE' section text."""
    lines = [
        banner("2A. CHANGED-FILE REVIEW COVERAGE"),
        f"Changed target files:          {len(coverage['rows'])}",
        f"Changed target text files:     "
        f"{coverage['changed_target_text_count']}",
        f"Merged changed target files:   "
        f"{coverage['merged_changed_target_text_count']}",
        f"Missing changed target files:  "
        f"{len(coverage['missing_changed_target_files'])}",
        "",
        "GATE: P4-REVIEW-COVERAGE-01",
        f"Rule: {coverage['rule']}",
        "",
    ]
    for finding in coverage_findings(coverage, mode):
        lines.append(finding.render())
    lines.append("")
    lines.append("Changed file index (Git Diff <-> Manifest <-> Merged "
                 "Content):")
    lines.append("")
    for row in coverage["rows"]:
        kind = row.get("kind", "?")
        if kind == "binary":
            lines.append(f"B  {row['rel']} merged=no  "
                         f"<binary; explicit exclusion>")
        elif kind == "oversized":
            lines.append(f"O  {row['rel']} merged=yes sha256="
                         f"{row.get('sha256', '')[:16]}  "
                         f"<oversized>")
        elif kind == "text_missing":
            lines.append(f"!  {row['rel']} merged=no  "
                         f"sha256={row.get('sha256', '')[:16]}")
        else:
            lines.append(f"A  {row['rel']} merged=yes sha256="
                         f"{row.get('sha256', '')[:16]}")
    if not coverage["rows"]:
        lines.append("(no changed files under target_root)")
    return "\n".join(lines) + "\n"


def validate_structure(
    project_root: Path,
    target_root: Path,
    mode: str,
) -> list[Finding]:
    findings: list[Finding] = []

    all_rels = [
        relpath(p, target_root)
        for p in iter_all_eligible(target_root, max_file_bytes=10_000_000)
    ]
    low_rels = [r.lower() for r in all_rels]

    def has_any(tokens: Sequence[str]) -> bool:
        return any(any(tok in rel for tok in tokens) for rel in low_rels)

    capability_checks = [
        (
            "P4-STRUCT-01",
            ("backtest/", "backtest_", "historical_replay", "historical-replay"),
            "Backtest / historical replay implementation",
        ),
        (
            "P4-STRUCT-02",
            ("ablation",),
            "Ablation framework",
        ),
        (
            "P4-STRUCT-03",
            ("oos", "walk_forward", "walk-forward", "out_of_sample"),
            "OOS / walk-forward validation",
        ),
        (
            "P4-STRUCT-04",
            ("robustness", "sensitivity", "perturb"),
            "Robustness / sensitivity validation",
        ),
        (
            "P4-STRUCT-05",
            ("cost", "slippage", "execution"),
            "Cost / execution validation",
        ),
        (
            "P4-STRUCT-06",
            ("regime",),
            "Regime validation",
        ),
        (
            "P4-STRUCT-07",
            ("practical", "retail"),
            "Retail practicality validation",
        ),
        (
            "P4-STRUCT-08",
            ("failure", "false_entry", "loss_cluster"),
            "Failure analysis",
        ),
        (
            "P4-STRUCT-09",
            ("tests/phase4/", "test_phase4", "phase4_test"),
            "Phase 4 tests",
        ),
    ]

    for code, tokens, label in capability_checks:
        if has_any(tokens):
            findings.append(Finding("PASS", code, "", f"{label} detected."))
        else:
            sev = "ERROR" if mode == "acceptance" else "WARN"
            findings.append(
                Finding(sev, code, "", f"{label} not detected by path/name heuristics.")
            )

    # Acceptance artifacts become hard requirements only in acceptance mode.
    # They live in <project>/audit/phase4 (outside target_root), so scan the
    # bounded audit directory rather than rglob the whole repository.
    audit_dir = project_root / "audit" / "phase4"
    existing_names: set[str] = set()
    if audit_dir.exists():
        for p in audit_dir.rglob("*"):
            if p.is_file():
                existing_names.add(p.name.lower())
    missing = [
        n for n in ACCEPTANCE_EVIDENCE_NAMES
        if n.lower() not in existing_names
    ]
    if mode == "acceptance":
        if missing:
            findings.append(
                Finding(
                    "ERROR",
                    "P4-STRUCT-10",
                    "",
                    "Missing acceptance evidence artifacts: " + ", ".join(missing),
                )
            )
        else:
            findings.append(
                Finding(
                    "PASS",
                    "P4-STRUCT-10",
                    "",
                    "All named Phase 4 acceptance evidence artifacts detected.",
                )
            )
    else:
        findings.append(
            Finding(
                "INFO",
                "P4-STRUCT-10",
                "",
                f"Acceptance artifacts currently missing: {len(missing)} "
                "(allowed in development mode).",
            )
        )

    return findings


def protected_phase3_changes(
    root: Path,
    target_root: Path,
    baseline: str,
    changes: Sequence[GitChange],
) -> list[Finding]:
    findings: list[Finding] = []

    if not git_available(root):
        return [
            Finding(
                "WARN",
                "P4-FROZEN-00",
                "",
                "Git unavailable; frozen Phase 3 modification check could not run.",
            )
        ]
    if not git_commit_exists(root, baseline):
        return [
            Finding(
                "ERROR",
                "P4-FROZEN-00",
                "",
                f"Frozen baseline '{baseline}' not found; source binding cannot be verified.",
            )
        ]

    if not git_is_ancestor(root, baseline, "HEAD"):
        findings.append(
            Finding(
                "ERROR",
                "P4-FROZEN-00A",
                "",
                f"Baseline '{baseline}' is not an ancestor of HEAD. "
                "Do not trust Phase3-vs-Phase4 diff/binding until the correct frozen baseline is supplied.",
            )
        )

    target_prefix = relpath(target_root, root).rstrip("/")
    hits = 0
    for c in changes:
        rel = c.path.replace("\\", "/")
        old_rel = (c.old_path or rel).replace("\\", "/")

        if target_prefix and not (
            rel == target_prefix or rel.startswith(target_prefix + "/")
            or old_rel == target_prefix or old_rel.startswith(target_prefix + "/")
        ):
            continue

        rel_for_match = rel[len(target_prefix):].lstrip("/") if target_prefix else rel
        old_for_match = old_rel[len(target_prefix):].lstrip("/") if target_prefix else old_rel
        matches = path_matches(rel_for_match, PROTECTED_PHASE3_AUTHORITY_PATTERNS) or path_matches(
            old_for_match, PROTECTED_PHASE3_AUTHORITY_PATTERNS
        )
        existed = git_file_existed_at(root, baseline, old_rel)

        # New Phase4 files are not Phase3 mutations even if placed under a broad package.
        if matches and existed and c.status[0] in {"M", "D", "R", "T"}:
            hits += 1
            findings.append(
                Finding(
                    "BLOCKER",
                    "P4-FROZEN-01",
                    rel,
                    f"Existing frozen Phase 3 authority surface changed since {baseline} "
                    f"(git status={c.status}). Requires explicit Phase 3 reopen/P0-P1 handling.",
                )
            )

    if hits == 0:
        findings.append(
            Finding(
                "PASS",
                "P4-FROZEN-01",
                "",
                f"No protected Phase 3 authority-surface modifications detected since {baseline}.",
            )
        )
    return findings


def scan_source_boundaries(files: Sequence[Path], root: Path) -> list[Finding]:
    findings: list[Finding] = []
    phase4_py = [
        p for p in files
        if p.suffix.lower() == ".py" and phase4_relevant(relpath(p, root))
    ]

    # Heuristics intentionally favor visibility over certainty.
    alt_authority_re = re.compile(
        r"^\s*def\s+(decide|make_decision|finalize_target|canonical_decision|"
        r"generate_(?:buy|sell)_signal)\s*\(",
        re.IGNORECASE | re.MULTILINE,
    )
    future_patterns = [
        (re.compile(r"\.shift\s*\(\s*-\d+", re.IGNORECASE), "negative shift"),
        (re.compile(r"\b(?:lead|future_value|future_price)\s*\(", re.IGNORECASE), "future/lead helper"),
        (re.compile(r"\biloc\s*\[[^\]]*\+\s*1[^\]]*\]", re.IGNORECASE), "forward iloc access"),
    ]
    decision_call_re = re.compile(
        r"(decision(?:\.engine)?\.evaluate\s*\(|\bevaluate\s*\([^)]*backtest|"
        r"canonical.*evaluate\s*\()",
        re.IGNORECASE,
    )

    any_backtest = False
    canonical_call_seen = False

    for path in phase4_py:
        rel = relpath(path, root)
        low = rel.lower()
        try:
            text = read_text(path)
        except Exception as exc:
            findings.append(
                Finding("WARN", "P4-STATIC-00", rel, f"Could not scan text: {exc}")
            )
            continue

        is_backtest = "backtest" in low or "replay" in low
        is_report = "report" in low or "summary" in low
        is_oos = (
            "/oos" in "/" + low
            or "walk_forward" in low
            or "walk-forward" in low
            or "out_of_sample" in low
        )

        if is_backtest:
            any_backtest = True
            if decision_call_re.search(text):
                canonical_call_seen = True

        m = alt_authority_re.search(text)
        if m and ("adapter" not in low and "contract" not in low):
            findings.append(
                Finding(
                    "WARN",
                    "P4-STATIC-01",
                    rel,
                    f"Possible alternate decision-authority function '{m.group(1)}'. "
                    "Review against P4-INV-001.",
                )
            )

        for regex, label in future_patterns:
            if regex.search(text):
                findings.append(
                    Finding(
                        "WARN",
                        "P4-STATIC-02",
                        rel,
                        f"Potential PIT leakage construct detected ({label}); manual review required.",
                    )
                )

        if is_oos and re.search(
            r"\b(fit|optimi[sz]e|grid_search|select_threshold|tune)\s*\(",
            text,
            re.IGNORECASE,
        ):
            findings.append(
                Finding(
                    "WARN",
                    "P4-STATIC-03",
                    rel,
                    "OOS/walk-forward module appears to contain fitting/tuning logic. "
                    "Verify OOS isolation and window chronology.",
                )
            )

        if is_report and re.search(
            r"\b(finalize_target|make_decision|canonical_decision|decision\.engine\.evaluate)\s*\(",
            text,
            re.IGNORECASE,
        ):
            findings.append(
                Finding(
                    "WARN",
                    "P4-STATIC-04",
                    rel,
                    "Report/summary code appears to invoke decision logic. "
                    "Report must remain a projection of recorded facts.",
                )
            )

        if re.search(r"\b(random|numpy\.random|np\.random)\b", text) and not re.search(
            r"\b(seed|random_state|rng)\b", text, re.IGNORECASE
        ):
            findings.append(
                Finding(
                    "WARN",
                    "P4-STATIC-05",
                    rel,
                    "Randomness detected without an obvious seed/random_state binding.",
                )
            )

        if "ablation" in low:
            # This cannot prove isolation, but flags suspicious mutation vocabulary.
            if re.search(
                r"\b(permission|wave|fsm|governance).*(setattr|monkeypatch|patch\.object)",
                text,
                re.IGNORECASE | re.DOTALL,
            ):
                findings.append(
                    Finding(
                        "INFO",
                        "P4-STATIC-06",
                        rel,
                        "Ablation implementation mutates/patches component behavior; "
                        "verify single-component neutralisation and restoration.",
                    )
                )

    if any_backtest:
        if canonical_call_seen:
            findings.append(
                Finding(
                    "PASS",
                    "P4-STATIC-07",
                    "",
                    "Canonical decision evaluation call detected in Phase 4 backtest/replay surface.",
                )
            )
        else:
            findings.append(
                Finding(
                    "WARN",
                    "P4-STATIC-07",
                    "",
                    "Backtest/replay files detected but no obvious canonical decision evaluation "
                    "call was found. Verify there is no duplicated decision path.",
                )
            )

    if not any(f.severity in {"WARN", "ERROR", "BLOCKER"} for f in findings):
        findings.append(
            Finding(
                "PASS",
                "P4-STATIC-99",
                "",
                "No heuristic Phase 4 boundary/PIT warnings detected.",
            )
        )
    return findings


def find_pytest_targets(project_root: Path, target_root: Path, scope: str) -> list[str]:
    """Discover Phase4 tests primarily inside the selected target subtree."""
    if scope == "full":
        return []

    candidates: list[str] = []
    selected_dirs: list[Path] = []

    def add_path(path: Path) -> None:
        if not path.exists():
            return
        rp = relpath(path, project_root)
        if rp not in candidates:
            candidates.append(rp)
        if path.is_dir():
            selected_dirs.append(path.resolve())

    def already_covered(path: Path) -> bool:
        resolved = path.resolve()
        for d in selected_dirs:
            try:
                resolved.relative_to(d)
                return True
            except ValueError:
                pass
        return False

    search_roots: list[Path] = []
    for td in (target_root / "tests", project_root / "tests"):
        if td.exists() and td not in search_roots:
            search_roots.append(td)

    # Explicit locations inside QCFP-MTF get highest priority.
    for rel in ("tests/phase4", "tests/backtest", "tests/validation"):
        add_path(target_root / rel)

    keywords = (
        "phase4", "phase_4", "backtest", "historical_replay", "replay_backtest",
        "ablation", "oos", "out_of_sample", "walk_forward", "robustness",
        "sensitivity", "slippage", "execution_cost", "regime", "practicality",
        "failure_analysis",
    )
    for tests_dir in search_roots:
        for path in sorted(tests_dir.rglob("test_*.py")):
            low = path.as_posix().lower()
            # Repository-level tests are included only when their path/name clearly targets Phase4.
            if any(k in low for k in keywords) and not already_covered(path):
                add_path(path)

    if scope == "targeted":
        # Frozen decision/governance regressions inside the QCFP-MTF target.
        for rel in (
            "tests/decision", "tests/governance",
            "tests/test_decision.py", "tests/test_governance.py",
        ):
            add_path(target_root / rel)

        target_tests = target_root / "tests"
        if target_tests.exists():
            for path in sorted(target_tests.rglob("test_*.py")):
                low = path.as_posix().lower()
                if any(k in low for k in ("decision", "governance")) and not already_covered(path):
                    add_path(path)

    return candidates


def run_pytest(
    project_root: Path,
    target_root: Path,
    scope: str,
    extra_args: Sequence[str],
    allow_fallback: bool = True,
) -> tuple[int, str, list[str], str, bool]:
    """Run pytest from project_root, selecting tests associated with target_root."""
    targets = find_pytest_targets(project_root, target_root, scope)
    actual_scope = scope
    fallback_used = False
    cmd = [sys.executable, "-m", "pytest", "-q"]

    if scope != "full":
        if targets:
            cmd.extend(targets)
        elif allow_fallback:
            actual_scope = f"full (fallback from {scope})"
            fallback_used = True
        else:
            return (
                5,
                "[review-tool] No explicit pytest targets were auto-detected for "
                f"scope={scope}. Pytest was NOT executed. Use --pytest-scope full, "
                "or remove --no-pytest-fallback, or place tests in a discoverable layout.",
                [],
                f"{scope} (not executed)",
                False,
            )

    cmd.extend(extra_args)
    rc, out = run(cmd, project_root, timeout=3600)

    prefix = ""
    if fallback_used:
        prefix = (
            "[review-tool] No explicit Phase 4/targeted pytest paths were found for "
            f"target={target_root}.\n"
            f"[review-tool] Automatically ran the FULL pytest suite instead "
            f"(requested scope={scope}).\n\n"
        )
    return rc, prefix + out, targets, actual_scope, fallback_used


def line_numbered(text: str) -> str:
    lines = text.splitlines()
    width = max(4, len(str(len(lines))))
    return "\n".join(f"{i:>{width}} | {line}" for i, line in enumerate(lines, 1))


def summarize_findings(findings: Sequence[Finding]) -> dict[str, int]:
    result: dict[str, int] = {}
    for f in findings:
        result[f.severity] = result.get(f.severity, 0) + 1
    return result


def render_git_section(root: Path, target_root: Path, baseline: str) -> str:
    if not git_available(root):
        return "Git repository: NOT DETECTED\n"

    branch = git_text(root, "branch", "--show-current") or "<detached>"
    head = git_text(root, "rev-parse", "HEAD")
    status = git_text(root, "status", "--short") or "<clean>"
    baseline_ok = git_commit_exists(root, baseline)
    target_rel = relpath(target_root, root)
    pathspec = target_rel if target_rel else "."

    if baseline_ok:
        baseline_full = git_text(root, "rev-parse", baseline)
        merge_base = git_text(root, "merge-base", baseline, "HEAD")
        rc, diff_stat = run(
            ["git", "diff", "--stat", baseline, "--", pathspec],
            root, timeout=120,
        )
        if rc != 0:
            diff_stat = f"<target-scoped git diff failed rc={rc}>\n{diff_stat}"
        elif not diff_stat:
            diff_stat = "<no target diff>"
        rc, name_status = run(
            ["git", "diff", "--name-status", "--find-renames", baseline, "--", pathspec],
            root, timeout=120,
        )
        if rc != 0:
            name_status = f"<target-scoped git diff failed rc={rc}>\n{name_status}"
        elif not name_status:
            name_status = "<no target diff>"
    else:
        baseline_full = "<not found>"
        merge_base = "<unavailable>"
        diff_stat = "<unavailable>"
        name_status = "<unavailable>"

    return "\n".join(
        [
            f"Branch:       {branch}",
            f"HEAD:         {head}",
            f"Baseline:     {baseline} -> {baseline_full}",
            f"Merge base:   {merge_base}",
            f"Target path:  {target_rel or '.'}",
            "",
            "Working tree (repository-wide):",
            status,
            "",
            f"Target diff vs {baseline} (current working tree):",
            diff_stat,
            "",
            "Target name/status:",
            name_status,
        ]
    )


def build_manifest(files: Sequence[Path], root: Path) -> list[dict[str, object]]:
    manifest = []
    for p in files:
        try:
            manifest.append(
                {
                    "path": relpath(p, root),
                    "bytes": p.stat().st_size,
                    "sha256": sha256_file(p),
                }
            )
        except OSError as exc:
            manifest.append(
                {
                    "path": str(p),
                    "bytes": None,
                    "sha256": None,
                    "error": str(exc),
                }
            )
    return manifest


def banner(title: str, char: str = "=") -> str:
    return f"\n{char * 88}\n{title}\n{char * 88}\n"


def main() -> int:
    args = parse_args()
    root = discover_project_root(args.project_root)
    target_root = resolve_target_root(root, args.target_root)

    output = (
        args.output.expanduser()
        if args.output
        else root
        / "Merged_Code"
        / f"merged_phase4_{args.mode}_review.txt"
    )
    if not output.is_absolute():
        output = (root / output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("PHASE 4 DEVELOPMENT / VALIDATION REVIEW TOOL")
    print("=" * 80)
    print(f"Mode:         {args.mode}")
    print(f"Project root: {root}")
    print(f"Target root:  {target_root}")
    print(f"Baseline:     {args.baseline}")
    print(f"Scope:        {args.scope}")
    print(f"Output:       {output}")
    print("=" * 80)

    changes = parse_git_changes(root, args.baseline)

    findings: list[Finding] = []
    findings.extend(protected_phase3_changes(root, target_root, args.baseline, changes))

    if not args.skip_structure_validation:
        findings.extend(
            validate_structure(root, target_root, args.mode)
        )

    files = collect_review_files(
        project_root=root,
        target_root=target_root,
        baseline=args.baseline,
        scope=args.scope,
        max_file_bytes=args.max_file_bytes,
    )

    # Never self-include the output if it happens to sit outside the normal excluded dir.
    files = [p for p in files if p.resolve() != output.resolve()]

    # P1-REV-01: changed-file coverage gate.
    merged_rels = {
        relpath(p, root).replace("\\", "/")
        for p in files
    }
    coverage = changed_target_records(
        project_root=root,
        target_root=target_root,
        changes=changes,
        untracked_rels=current_untracked_files(root),
        merged_rels=merged_rels,
        max_file_bytes=args.max_file_bytes,
    )
    findings.extend(coverage_findings(coverage, args.mode))

    if not args.skip_static_boundary_validation:
        findings.extend(scan_source_boundaries(files, root))

    pytest_rc: int | None = None
    pytest_out = ""
    pytest_targets: list[str] = []
    pytest_actual_scope = args.pytest_scope
    pytest_fallback_used = False
    if args.run_pytest:
        print("Running pytest...")
        (
            pytest_rc,
            pytest_out,
            pytest_targets,
            pytest_actual_scope,
            pytest_fallback_used,
        ) = run_pytest(
            root,
            target_root,
            args.pytest_scope,
            args.pytest_extra_arg,
            allow_fallback=not args.no_pytest_fallback,
        )
        sev = "PASS" if pytest_rc == 0 else "ERROR"
        display_targets = (
            pytest_targets
            if pytest_targets
            else (["<full suite>"] if pytest_actual_scope.startswith("full") else ["<none>"])
        )
        findings.append(
            Finding(
                sev,
                "P4-PYTEST-01",
                "",
                f"pytest return code = {pytest_rc}; requested_scope={args.pytest_scope}; "
                f"actual_scope={pytest_actual_scope}; targets={display_targets}",
            )
        )
        if pytest_fallback_used:
            findings.append(
                Finding(
                    "INFO",
                    "P4-PYTEST-02",
                    "",
                    "Targeted test paths were not auto-detected; full-suite fallback was used.",
                )
            )

    manifest = build_manifest(files, root)
    manifest_hash = hashlib.sha256(
        json.dumps(manifest, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()

    counts = summarize_findings(findings)
    now = datetime.now(timezone.utc).astimezone()

    parts: list[str] = []
    parts.append(
        "\n".join(
            [
                f"{root.name} PHASE 4 DEVELOPMENT / VALIDATION REVIEW BUNDLE",
                f"Tool version:            {TOOL_VERSION}",
                f"Generated at:            {now.isoformat()}",
                f"Project root:            {root}",
                f"Target root:             {target_root}",
                f"Mode:                    {args.mode}",
                f"Baseline:                {args.baseline}",
                f"Review scope:            {args.scope}",
                f"Files merged:            {len(files)}",
                f"Manifest SHA256:         {manifest_hash}",
                "",
                "GOVERNING RULE:",
                "Phase 4 validates Phase 3; Phase 4 does not redesign Phase 3.",
                "",
                "STATIC CHECK NOTE:",
                "Heuristic checks are review aids. PASS does not prove semantic correctness; "
                "WARN does not prove a defect.",
            ]
        )
    )

    parts.append(banner("1. GIT / SOURCE IDENTITY"))
    parts.append(render_git_section(root, target_root, args.baseline))

    parts.append(banner("2. PHASE 4 PRE-REVIEW FINDINGS"))
    counts_line = " | ".join(
        f"{k}={counts.get(k, 0)}"
        for k in ("PASS", "INFO", "WARN", "ERROR", "BLOCKER")
    )
    parts.append(counts_line)
    parts.append("")
    for f in findings:
        parts.append(f.render())

    parts.append(render_coverage_section(coverage, args.mode))

    parts.append(banner("3. PYTEST"))
    if args.run_pytest:
        parts.append(
            f"pytest requested scope: {args.pytest_scope}\n"
            f"pytest actual scope: {pytest_actual_scope}\n"
            f"pytest targets: "
            f"{pytest_targets if pytest_targets else (['<full suite>'] if pytest_actual_scope.startswith('full') else ['<none>'])}\n"
            f"pytest return code: {pytest_rc}\n\n"
            f"{pytest_out or '<no output>'}"
        )
    else:
        parts.append(
            "NOT RUN. Re-run the merger with --run-pytest to bind test output "
            "into this review bundle."
        )

    parts.append(banner("4. FILE MANIFEST"))
    parts.append(
        json.dumps(
            {
                "tool_version": TOOL_VERSION,
                "baseline": args.baseline,
                "project_root": str(root),
                "target_root": str(target_root),
                "mode": args.mode,
                "scope": args.scope,
                "manifest_sha256": manifest_hash,
                "files": manifest,
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )

    parts.append(banner("5. MERGED REVIEW CONTENT"))
    for entry, path in zip(manifest, files):
        rp = str(entry["path"])
        parts.append(
            "\n".join(
                [
                    "",
                    "#" * 88,
                    f"FILE: {rp}",
                    f"SIZE: {entry.get('bytes')}",
                    f"SHA256: {entry.get('sha256')}",
                    "#" * 88,
                ]
            )
        )
        try:
            text = read_text(path)
            if not args.no_line_numbers:
                text = line_numbered(text)
            parts.append(text)
        except Exception as exc:
            parts.append(f"<UNREADABLE TEXT FILE: {type(exc).__name__}: {exc}>")

    parts.append(banner("6. REVIEW FOOTER"))
    parts.append(
        "\n".join(
            [
                f"Manifest SHA256: {manifest_hash}",
                f"Finding counts: {counts_line}",
                f"pytest rc: {pytest_rc if pytest_rc is not None else '<not run>'}",
                "",
                "Suggested review order:",
                "1) BLOCKER/ERROR findings",
                "2) Frozen Phase 3 diff",
                "3) Backtest/PIT contract",
                "4) Historical replay + execution separation",
                "5) Ablation isolation",
                "6) OOS/walk-forward leakage controls",
                "7) Robustness/cost/regime/practicality/failure analysis",
                "8) Evidence identity/binding",
                "9) Regression and acceptance judge",
            ]
        )
    )

    output.write_text("\n".join(parts), encoding="utf-8")

    for f in findings:
        if f.severity in {"BLOCKER", "ERROR"}:
            print(f.render())
        elif f.severity == "WARN":
            print(f.render())

    print("-" * 80)
    print(f"Merged {len(files)} review files")
    print(f"Manifest SHA256: {manifest_hash}")
    print(f"Review bundle written: {output}")

    has_blocking_findings = any(f.severity in {"BLOCKER", "ERROR"} for f in findings)
    pytest_failed = args.run_pytest and pytest_rc != 0

    if pytest_failed:
        print("RESULT: FAIL (pytest)")
        return 1
    if args.strict and has_blocking_findings:
        print("RESULT: FAIL (strict validation)")
        return 2

    if has_blocking_findings:
        print("RESULT: REVIEW REQUIRED (blocking findings present; use --strict to fail exit code)")
    else:
        print("RESULT: BUNDLE CREATED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
