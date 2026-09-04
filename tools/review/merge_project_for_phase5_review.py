#!/usr/bin/env python3
"""
QCFP-MTF Phase 5 Shadow Operation / Promotion Qualification review bundle builder.

Purpose
-------
Create a deterministic, review-oriented merged text bundle for Phase 5:
Shadow Runtime / Isolation / Canonical-vs-Shadow Divergence /
Decision Outcome Observation / Evidence Aging / Failure & Incident Governance /
Replay / Promotion Qualification / Acceptance Evidence.

Governing rules
---------------
1. Phase 5 observes and qualifies the frozen Phase 4 system; it does not redesign it.
2. Shadow has NO canonical or production authority.
3. Outcome observations must not leak into decision-time evaluation.
4. Promotion qualification is not promotion authority; Human approval remains final.
5. Review bundles bind Git/source identity, file hashes, frozen-surface findings,
   optional pytest output, and review-worthy source/evidence text.
6. Static checks are guardrails, not semantic proof. Human/AI review remains required.

Typical usage
-------------
# Development review (recommended while implementing P5-A ... P5-J)
python tools/review/merge_project_for_phase5_review.py --run-pytest

# Machine qualification review
python tools/review/merge_project_for_phase5_review.py \
    --mode qualification \
    --run-pytest \
    --pytest-scope full \
    --strict

# Final review after explicit Human approval artifact exists
python tools/review/merge_project_for_phase5_review.py \
    --mode final-acceptance \
    --run-pytest \
    --pytest-scope full

# Explicit repository/baseline
python tools/review/merge_project_for_phase5_review.py \
    --project-root C:\\path\\to\\QCFP_MTF \
    --baseline qcfp-mtf-phase4-frozen

Notes
-----
* Default frozen baseline is the Phase 4 frozen tag: qcfp-mtf-phase4-frozen.
* qualification mode requires the machine-readable Phase 5 qualification evidence
  package but does NOT require Human approval.
* final-acceptance additionally requires human_promotion_record.json and treats a
  dirty working tree as an error.
* This tool never changes code, creates Git commits/tags, approves promotion, or
  starts Phase 6.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence


TOOL_VERSION = "1.1.0"
DEFAULT_BASELINE = "qcfp-mtf-phase4-frozen"
DEFAULT_MANIFEST_REL = "audit/phase5/frozen_surface_manifest.json"

# Controlled full-regression deselections. Every entry must carry an explicit
# node and reason; the reviewer self-tests pin this exact set so it cannot
# silently expand. Phase 5 never modifies the frozen tests themselves.
GOVERNED_DESELECTIONS = (
    {
        "node": (
            "Core/QCFP_MTF/tests/test_governance/"
            "test_phase4_evidence_integrity.py::"
            "test_real_runner_builder_judge_pipeline"
        ),
        "reason": (
            "Phase 4 closure self-reference: the live builder→judge pipeline "
            "diffs cdcab0c..HEAD and is meaningful only while HEAD == Phase 4 "
            "frozen commit. Phase 4's own regression runner exposes "
            "--ignore-pipeline-test for this reason. Frozen test untouched."
        ),
    },
    {
        "node": (
            "Core/QCFP_MTF/tests/test_governance/test_phase1.py::"
            "test_phase1_acceptance_pending_baseline"
        ),
        "reason": (
            "Historical Phase 1 acceptance test calls phase1_acceptance() "
            "without out_dir and therefore regenerates frozen "
            "audit/phase1/phase1_acceptance.json. Phase 5 does not modify the "
            "frozen test; equivalent behavioral coverage is provided by "
            "Core/QCFP_MTF/tests/test_phase5/"
            "test_phase1_acceptance_isolation.py (out_dir=tmp_path)."
        ),
    },
)

TEXT_EXTENSIONS = {
    ".py", ".pyi", ".md", ".rst", ".txt",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".sql", ".csv",
}

# Never merge virtualenvs, caches, VCS internals, large generated outputs,
# or previous review bundles.
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

# Semantic discovery hints only; they do not define repository architecture.
PHASE5_PATH_HINTS = (
    "tests/phase5/",
    "test_phase5",
    "phase5_",
    "phase5/",
    "evidence/phase5",
    "phase5/evidence",
    "/shadow/",
    "shadow_",
    "/divergence/",
    "divergence_",
    "/observation/",
    "outcome_observation",
    "outcome_",
    "evidence_aging",
    "freshness",
    "/incidents/",
    "incident_",
    "/promotion/",
    "promotion_",
    "qualification",
)

REVIEW_ANCHOR_PATTERNS = (
    "pyproject.toml",
    "pytest.ini",
    "setup.cfg",
    "tox.ini",
    "requirements*.txt",
    "**/*phase5*.md",
    "**/*phase_5*.md",
    "**/*phase5*.yaml",
    "**/*phase5*.yml",
    "**/*phase5*.json",
    "**/decision/engine.py",
    "**/decision_engine.py",
    "**/finalize_target.py",
    "**/ledger.py",
    "**/replay.py",
    "**/tests/phase5/**/*.py",
    "**/tests/**/test_*phase5*.py",
    "**/shadow/**/*.py",
    "**/divergence/**/*.py",
    "**/observation/**/*.py",
    "**/incidents/**/*.py",
    "**/promotion/**/*.py",
    "**/evidence/**/*phase5*.py",
    "**/governance/**/*phase5*.py",
)

# Machine qualification evidence. These are required in qualification and
# final-acceptance modes. Human approval is deliberately not included here.
QUALIFICATION_EVIDENCE_NAMES = (
    "phase5_manifest.json",
    "frozen_baseline_identity.json",
    "frozen_surface_manifest.json",
    "baseline_test_summary.json",
    "shadow_runtime_summary.json",
    "shadow_isolation_evidence.json",
    "divergence_summary.json",
    "unexplained_divergence_report.json",
    "outcome_observation_summary.json",
    "evidence_aging_summary.json",
    "incident_register.json",
    "replay_validation.json",
    "runtime_coverage.json",
    "promotion_gate_result.json",
    "changed_file_coverage.json",
    "pytest_summary.json",
    "phase5_acceptance_summary.json",
)

FINAL_ACCEPTANCE_EVIDENCE_NAMES = (
    "human_promotion_record.json",
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
    source: str = "committed"


@dataclass(frozen=True)
class FrozenSurfaceManifest:
    """Phase 5 Frozen Surface Manifest — single boundary authority.

    The reviewer must not maintain its own second set of frozen truth; it
    loads audit/phase5/frozen_surface_manifest.json and classifies every
    changed path (existing or new) against that manifest.
    """

    frozen: tuple[str, ...] = ()
    shared_read_only: tuple[str, ...] = ()
    phase5_allowed: tuple[str, ...] = ()
    out_of_scope: tuple[str, ...] = ()
    unknown: tuple[str, ...] = ()
    source_rel: str = ""


FROZEN = "FROZEN"
FROZEN_AUTHORITY = "FROZEN_AUTHORITY"
FROZEN_EVIDENCE = "FROZEN_EVIDENCE"
SHARED_READ_ONLY = "SHARED_READ_ONLY"
PHASE5_ALLOWED = "PHASE5_ALLOWED"
OUT_OF_SCOPE = "OUT_OF_SCOPE"
UNKNOWN = "UNKNOWN"


def _entry_paths(entries: object) -> list[str]:
    """Manifest sections are either [str] or [{path, role}, ...]."""
    out: list[str] = []
    for entry in entries or []:
        if isinstance(entry, str) and entry:
            out.append(entry)
        elif isinstance(entry, dict):
            p = entry.get("path")
            if isinstance(p, str) and p:
                out.append(p)
    return out


def load_frozen_surface_manifest(
    root: Path,
    rel: str = DEFAULT_MANIFEST_REL,
) -> tuple[FrozenSurfaceManifest | None, str]:
    """Load the Phase 5 frozen surface manifest.

    Returns (manifest, error_message). A missing/invalid manifest must fail
    closed: the reviewer is not allowed to invent its own frozen truth.
    """
    path = root / rel
    if not path.exists():
        return None, f"Frozen surface manifest missing: {rel}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"Frozen surface manifest unreadable ({rel}): {exc}"
    if not isinstance(data, dict):
        return None, f"Frozen surface manifest root must be an object ({rel})"
    frozen = tuple(_entry_paths(data.get("frozen")))
    shared = tuple(_entry_paths(data.get("shared_read_only")))
    allowed = tuple(_entry_paths(data.get("phase5_allowed_new_files")))
    oos = tuple(_entry_paths(data.get("out_of_scope_non_authority")))
    unknown = tuple(_entry_paths(data.get("unknown")))
    if not frozen and not shared:
        return None, (
            f"Frozen surface manifest has no frozen/shared_read_only "
            f"entries ({rel}); refusing to enforce an empty boundary."
        )
    return (
        FrozenSurfaceManifest(
            frozen=frozen,
            shared_read_only=shared,
            phase5_allowed=allowed,
            out_of_scope=oos,
            unknown=unknown,
            source_rel=rel,
        ),
        "",
    )


def classify_phase5_path(
    rel: str,
    manifest: FrozenSurfaceManifest | None,
) -> str:
    """Classify a repository path against the manifest.

    Classification order is significant: FROZEN > SHARED_READ_ONLY >
    PHASE5_ALLOWED > OUT_OF_SCOPE > UNKNOWN. Anything not declared by the
    manifest is UNKNOWN and must block.
    """
    rel = rel.replace("\\", "/")
    if manifest is None:
        return UNKNOWN
    if path_matches(rel, manifest.frozen):
        return FROZEN
    if path_matches(rel, manifest.shared_read_only):
        return SHARED_READ_ONLY
    if path_matches(rel, manifest.phase5_allowed):
        return PHASE5_ALLOWED
    if path_matches(rel, manifest.out_of_scope):
        return OUT_OF_SCOPE
    if path_matches(rel, manifest.unknown):
        return UNKNOWN
    return UNKNOWN


def frozen_subclass(rel: str) -> str:
    """FROZEN top-level subclass used only for clearer reporting."""
    rel = rel.replace("\\", "/")
    if path_matches(
        rel,
        (
            "audit/phase1/**",
            "audit/phase3/**",
            "audit/phase4/**",
            "audit/baseline/**",
        ),
    ):
        return FROZEN_EVIDENCE
    return FROZEN_AUTHORITY


def is_test_file(rel: str) -> bool:
    """Return True for test/regression sources (not decision-time runtime)."""
    rel = rel.replace("\\", "/")
    low = "/" + rel.lower()
    name = rel.rsplit("/", 1)[-1].lower()
    return (
        "/tests/" in low
        or "/test/" in low
        or name.startswith("test_")
        or name.endswith("_test.py")
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build a QCFP-MTF Phase 5 Shadow/Promotion review bundle."
    )
    p.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Project root. Default: auto-detect from script/current directory.",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Merged output file. Default: "
            "<project>/Merged_Code/merged_QCFP_MTF_phase5_<mode>_review.txt"
        ),
    )
    p.add_argument(
        "--mode",
        choices=("development", "qualification", "final-acceptance"),
        default="development",
        help=(
            "development = work-in-progress review; qualification = machine "
            "promotion-qualification evidence review; final-acceptance = after "
            "explicit Human approval artifact exists."
        ),
    )
    p.add_argument(
        "--baseline",
        default=DEFAULT_BASELINE,
        help=f"Frozen Phase 4 Git baseline/tag/commit. Default: {DEFAULT_BASELINE}",
    )
    p.add_argument(
        "--scope",
        choices=("phase5", "changed", "all"),
        default="phase5",
        help=(
            "phase5 = Phase5-relevant files + changed files + frozen anchors; "
            "changed = Git-changed files + anchors; all = all eligible text files."
        ),
    )
    p.add_argument(
        "--run-pytest",
        action="store_true",
        help="Run pytest and embed the result in the review bundle.",
    )
    p.add_argument(
        "--pytest-scope",
        choices=("phase5", "targeted", "full"),
        default="targeted",
        help=(
            "phase5 = Phase 5 tests only; targeted = Phase 5 plus frozen "
            "decision/governance/replay/Phase4 regressions when discoverable; "
            "full = entire pytest suite."
        ),
    )
    p.add_argument(
        "--pytest-extra-arg",
        action="append",
        default=[],
        help="Additional argument passed to pytest. May be specified multiple times.",
    )
    p.add_argument(
        "--skip-structure-validation",
        action="store_true",
        help="Skip Phase 5 structure/capability/evidence checks.",
    )
    p.add_argument(
        "--skip-static-boundary-validation",
        action="store_true",
        help="Skip heuristic Shadow/Authority/Future-Leakage/Promotion checks.",
    )
    p.add_argument(
        "--skip-git-baseline-validation",
        action="store_true",
        help="Skip Git baseline ancestry and working-tree review findings.",
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
        help=(
            "Exit non-zero for ERROR/BLOCKER findings in development mode. "
            "qualification/final-acceptance are strict automatically."
        ),
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
    return sum((path / marker).exists() for marker in markers) >= 2


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
    return any(fnmatch.fnmatch(path.name, pat) for pat in EXCLUDED_FILE_GLOBS)


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
    low = rel.lower()
    return any(
        fnmatch.fnmatch(rel, pat)
        or fnmatch.fnmatch("/" + rel, pat)
        or fnmatch.fnmatch(low, pat.lower())
        or fnmatch.fnmatch("/" + low, pat.lower())
        for pat in patterns
    )


def phase5_relevant(rel: str) -> bool:
    low = "/" + rel.lower().replace("\\", "/")
    return any(hint.lower() in low for hint in PHASE5_PATH_HINTS)


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
    rc, _ = run(["git", "merge-base", "--is-ancestor", ancestor, descendant], root, timeout=30)
    return rc == 0


def git_file_existed_at(root: Path, baseline: str, rel: str) -> bool:
    rc, _ = run(["git", "cat-file", "-e", f"{baseline}:{rel}"], root, timeout=30)
    return rc == 0


def parse_name_status_output(out: str, source: str) -> list[GitChange]:
    changes: list[GitChange] = []
    for raw in out.splitlines():
        if not raw.strip():
            continue
        cols = raw.split("\t")
        status = cols[0]
        if status.startswith(("R", "C")) and len(cols) >= 3:
            changes.append(
                GitChange(status=status, old_path=cols[1], path=cols[2], source=source)
            )
        elif len(cols) >= 2:
            changes.append(GitChange(status=status, path=cols[1], source=source))
    return changes


def parse_committed_changes(root: Path, baseline: str) -> list[GitChange]:
    if not git_available(root) or not git_commit_exists(root, baseline):
        return []
    rc, out = run(
        [
            "git",
            "-c",
            "core.quotepath=false",
            "diff",
            "--name-status",
            "--find-renames",
            f"{baseline}...HEAD",
        ],
        root,
        timeout=120,
    )
    return parse_name_status_output(out, "committed") if rc == 0 else []


def parse_worktree_changes(root: Path) -> list[GitChange]:
    if not git_available(root):
        return []
    changes: list[GitChange] = []
    for source, cmd in (
        (
            "staged",
            [
                "git",
                "-c",
                "core.quotepath=false",
                "diff",
                "--cached",
                "--name-status",
                "--find-renames",
            ],
        ),
        (
            "unstaged",
            [
                "git",
                "-c",
                "core.quotepath=false",
                "diff",
                "--name-status",
                "--find-renames",
            ],
        ),
    ):
        rc, out = run(cmd, root, timeout=120)
        if rc == 0:
            changes.extend(parse_name_status_output(out, source))
    return changes


def current_untracked_files(root: Path) -> list[str]:
    if not git_available(root):
        return []
    rc, out = run(
        [
            "git",
            "-c",
            "core.quotepath=false",
            "ls-files",
            "--others",
            "--exclude-standard",
        ],
        root,
        timeout=60,
    )
    if rc != 0:
        return []
    return [line.strip().replace("\\", "/") for line in out.splitlines() if line.strip()]


def combine_changes(*groups: Sequence[GitChange]) -> list[GitChange]:
    seen: set[tuple[str, str, str | None, str]] = set()
    result: list[GitChange] = []
    for group in groups:
        for change in group:
            key = (change.status, change.path, change.old_path, change.source)
            if key in seen:
                continue
            seen.add(key)
            result.append(change)
    return result


def iter_all_eligible(root: Path, max_file_bytes: int) -> Iterable[Path]:
    for path in root.rglob("*"):
        if eligible_text_file(path, max_file_bytes):
            yield path


def collect_review_files(
    root: Path,
    baseline: str,
    scope: str,
    max_file_bytes: int,
) -> list[Path]:
    all_files = list(iter_all_eligible(root, max_file_bytes))
    by_rel = {relpath(path, root): path for path in all_files}

    if scope == "all":
        return sorted(all_files, key=lambda p: relpath(p, root).lower())

    committed = parse_committed_changes(root, baseline)
    worktree = parse_worktree_changes(root)
    changed_rels = {
        c.path.replace("\\", "/")
        for c in combine_changes(committed, worktree)
        if c.status and c.status[0] != "D"
    }
    changed_rels.update(current_untracked_files(root))

    selected: set[Path] = set()
    for rel, path in by_rel.items():
        if rel in changed_rels:
            selected.add(path)
        if path_matches(rel, REVIEW_ANCHOR_PATTERNS):
            selected.add(path)

    if scope == "phase5":
        for rel, path in by_rel.items():
            if phase5_relevant(rel):
                selected.add(path)

    return sorted(selected, key=lambda p: relpath(p, root).lower())


def validate_git_baseline(root: Path, baseline: str, mode: str) -> list[Finding]:
    findings: list[Finding] = []
    if not git_available(root):
        return [
            Finding(
                "ERROR",
                "P5-GIT-00",
                "",
                "Git repository not detected; frozen baseline/source identity cannot be verified.",
            )
        ]

    if not git_commit_exists(root, baseline):
        return [
            Finding(
                "ERROR",
                "P5-GIT-01",
                "",
                f"Frozen Phase 4 baseline '{baseline}' not found.",
            )
        ]

    if git_is_ancestor(root, baseline, "HEAD"):
        findings.append(
            Finding(
                "PASS",
                "P5-GIT-02",
                "",
                f"Frozen baseline '{baseline}' is an ancestor of HEAD.",
            )
        )
    else:
        findings.append(
            Finding(
                "BLOCKER",
                "P5-GIT-02",
                "",
                f"Frozen baseline '{baseline}' is NOT an ancestor of HEAD; source lineage is invalid.",
            )
        )

    worktree = parse_worktree_changes(root)
    untracked = current_untracked_files(root)
    if worktree:
        sev = "ERROR" if mode == "final-acceptance" else "WARN"
        findings.append(
            Finding(
                sev,
                "P5-GIT-03",
                "",
                f"Tracked working-tree changes detected: {len(worktree)} entries. "
                "They are included in frozen-surface checks.",
            )
        )
    else:
        findings.append(Finding("PASS", "P5-GIT-03", "", "No tracked working-tree changes."))

    if untracked:
        sev = "ERROR" if mode == "final-acceptance" else ("WARN" if mode == "qualification" else "INFO")
        findings.append(
            Finding(
                sev,
                "P5-GIT-04",
                "",
                f"Untracked files detected: {len(untracked)}. Review bundle includes eligible files when relevant.",
            )
        )
    else:
        findings.append(Finding("PASS", "P5-GIT-04", "", "No untracked files detected."))

    return findings


def validate_structure(root: Path, mode: str) -> list[Finding]:
    findings: list[Finding] = []
    all_rels = [
        relpath(path, root)
        for path in iter_all_eligible(root, max_file_bytes=10_000_000)
    ]
    low_rels = [rel.lower() for rel in all_rels]

    def has_any(tokens: Sequence[str]) -> bool:
        return any(any(token in rel for token in tokens) for rel in low_rels)

    capability_checks = [
        (
            "P5-STRUCT-01",
            ("/shadow/", "shadow_runtime", "shadow_run", "shadow_decision"),
            "Shadow runtime / shadow identity surface",
        ),
        (
            "P5-STRUCT-02",
            ("shadow_isolation", "isolation", "boundary_guard", "no_write_guard"),
            "Shadow isolation / authority guard",
        ),
        (
            "P5-STRUCT-03",
            ("/divergence/", "divergence_", "divergence"),
            "Canonical-vs-Shadow divergence framework",
        ),
        (
            "P5-STRUCT-04",
            ("/observation/", "outcome_observation", "outcome_", "observation_horizon"),
            "Decision outcome observation",
        ),
        (
            "P5-STRUCT-05",
            ("evidence_aging", "freshness", "evidence_age", "stale_evidence"),
            "Evidence aging / freshness governance",
        ),
        (
            "P5-STRUCT-06",
            ("/incidents/", "incident_", "incident_registry", "failure_taxonomy"),
            "Failure / incident qualification",
        ),
        (
            "P5-STRUCT-07",
            ("/promotion/", "promotion_gate", "promotion_qualification", "qualification"),
            "Promotion qualification gate",
        ),
        (
            "P5-STRUCT-08",
            ("replay_validation", "shadow_replay", "replay"),
            "Replay / audit validation",
        ),
        (
            "P5-STRUCT-09",
            ("tests/phase5/", "test_phase5", "phase5_test"),
            "Phase 5 tests",
        ),
    ]

    for code, tokens, label in capability_checks:
        if has_any(tokens):
            findings.append(Finding("PASS", code, "", f"{label} detected."))
        else:
            sev = "ERROR" if mode in {"qualification", "final-acceptance"} else "WARN"
            findings.append(
                Finding(sev, code, "", f"{label} not detected by path/name heuristics.")
            )

    existing_names = {Path(rel).name.lower() for rel in all_rels}
    missing_qualification = [
        name for name in QUALIFICATION_EVIDENCE_NAMES if name.lower() not in existing_names
    ]

    if mode in {"qualification", "final-acceptance"}:
        if missing_qualification:
            findings.append(
                Finding(
                    "ERROR",
                    "P5-STRUCT-10",
                    "",
                    "Missing machine qualification evidence artifacts: "
                    + ", ".join(missing_qualification),
                )
            )
        else:
            findings.append(
                Finding(
                    "PASS",
                    "P5-STRUCT-10",
                    "",
                    "All named Phase 5 machine qualification evidence artifacts detected.",
                )
            )
    else:
        findings.append(
            Finding(
                "INFO",
                "P5-STRUCT-10",
                "",
                f"Machine qualification artifacts currently missing: {len(missing_qualification)} "
                "(allowed in development mode).",
            )
        )

    missing_human = [
        name for name in FINAL_ACCEPTANCE_EVIDENCE_NAMES if name.lower() not in existing_names
    ]
    if mode == "final-acceptance":
        if missing_human:
            findings.append(
                Finding(
                    "ERROR",
                    "P5-STRUCT-11",
                    "",
                    "Final acceptance requires explicit Human approval artifact(s): "
                    + ", ".join(missing_human),
                )
            )
        else:
            findings.append(
                Finding(
                    "PASS",
                    "P5-STRUCT-11",
                    "",
                    "Human promotion record detected for final acceptance review.",
                )
            )
    elif mode == "qualification":
        if missing_human:
            findings.append(
                Finding(
                    "PASS",
                    "P5-STRUCT-11",
                    "",
                    "Human promotion record is not required in qualification mode; "
                    "machine qualification must stop before Human authority.",
                )
            )
        else:
            findings.append(
                Finding(
                    "INFO",
                    "P5-STRUCT-11",
                    "",
                    "Human promotion record already exists; verify it was created only after explicit Human review.",
                )
            )

    return findings


def enforce_frozen_surface(
    root: Path,
    baseline: str,
    changes: Sequence[GitChange],
    mode: str,
    manifest: FrozenSurfaceManifest | None,
) -> list[Finding]:
    """Manifest-driven frozen surface enforcement.

    Every changed path — committed, staged, unstaged, renamed, deleted,
    type-changed, or untracked/new — is classified against the manifest.
    A new file inside a FROZEN / SHARED_READ_ONLY / UNKNOWN path is a BLOCKER
    even though it did not exist at the frozen baseline (no second Authority).
    """

    findings: list[Finding] = []
    if not git_available(root):
        return [
            Finding(
                "ERROR",
                "P5-FROZEN-00",
                "",
                "Git unavailable; frozen Phase 4 surface check could not run.",
            )
        ]
    if not git_commit_exists(root, baseline):
        return [
            Finding(
                "ERROR",
                "P5-FROZEN-00",
                "",
                f"Frozen baseline '{baseline}' not found; frozen-surface binding cannot be verified.",
            )
        ]
    if manifest is None:
        return [
            Finding(
                "ERROR",
                "P5-FROZEN-00",
                DEFAULT_MANIFEST_REL,
                "Frozen surface manifest could not be loaded; reviewer must not "
                "enforce its own second frozen truth. Fail closed until the "
                "manifest is present and readable.",
            )
        ]

    frozen_hits = 0
    shared_hits = 0
    unknown_hits = 0
    allowed_hits = 0
    oos_hits = 0
    reported: set[tuple[str, str]] = set()
    rows: list[str] = []

    def add(severity: str, code: str, path: str, message: str) -> None:
        key = (code, path)
        if key in reported:
            return
        reported.add(key)
        findings.append(Finding(severity, code, path, message))

    for change in changes:
        rel = change.path.replace("\\", "/")
        old_rel = (change.old_path or rel).replace("\\", "/")
        status = change.status or "?"
        kind = status[0] if status else "?"
        existed = git_file_existed_at(root, baseline, old_rel)
        new_file = not existed

        cls_new = classify_phase5_path(rel, manifest)
        cls_old = classify_phase5_path(old_rel, manifest)

        endpoints = [(cls_new, rel)]
        if old_rel != rel:
            endpoints.append((cls_old, old_rel))
        for cls, cls_path in endpoints:
            if cls not in {FROZEN, SHARED_READ_ONLY, PHASE5_ALLOWED, OUT_OF_SCOPE, UNKNOWN}:
                cls = UNKNOWN
            origin = change.source
            base = (
                f"path={cls_path} status={status} source={origin} "
                f"class={cls} new_file={new_file}"
            )
            old_info = f" old={change.old_path}" if change.old_path else ""
            rows.append(base + old_info)

            if cls == FROZEN:
                frozen_hits += 1
                subclass = frozen_subclass(cls_path)
                if new_file:
                    add(
                        "BLOCKER",
                        "P5-FROZEN-01",
                        cls_path,
                        f"New file created inside a FROZEN surface ({subclass}); "
                        "new files still require path classification and cannot "
                        "establish a second Authority. Frozen-baseline reopen "
                        "review required before any Phase 5 work may use it. "
                        f"[{origin}]",
                    )
                else:
                    add(
                        "BLOCKER",
                        "P5-FROZEN-01",
                        cls_path,
                        f"Existing frozen {subclass} surface changed relative to "
                        f"{baseline} (status={status}, source={origin}). "
                        "Requires explicit frozen-baseline reopen/impact review; "
                        "Phase 5 must not silently fix it.",
                    )
            elif cls == SHARED_READ_ONLY:
                shared_hits += 1
                if new_file:
                    add(
                        "BLOCKER",
                        "P5-FROZEN-03",
                        cls_path,
                        "New file created inside a SHARED_READ_ONLY surface; "
                        "new files still require path classification. "
                        f"[{origin}]",
                    )
                else:
                    add(
                        "BLOCKER",
                        "P5-FROZEN-03",
                        cls_path,
                        "Existing SHARED_READ_ONLY surface changed relative to "
                        f"{baseline} (status={status}, source={origin}); "
                        "read-only shared modules must not be modified by Phase 5.",
                    )
            elif cls == UNKNOWN:
                unknown_hits += 1
                add(
                    "BLOCKER",
                    "P5-FROZEN-04",
                    cls_path,
                    "Changed path is UNKNOWN to the frozen surface manifest; "
                    "resolve the classification before any further Phase 5 work. "
                    f"[{origin}]",
                )
            elif cls == PHASE5_ALLOWED:
                allowed_hits += 1
                if new_file:
                    add(
                        "PASS",
                        "P5-FROZEN-06",
                        cls_path,
                        "New file on the declared PHASE5_ALLOWED surface; "
                        f"permitted as Phase 5 addition. [{origin}]",
                    )
                else:
                    sev = "ERROR" if mode in {"qualification", "final-acceptance"} else "WARN"
                    add(
                        sev,
                        "P5-FROZEN-07",
                        cls_path,
                        "Existing file matched PHASE5_ALLOWED but already existed "
                        "at the frozen baseline; modification must be explicitly "
                        "reviewed before it counts as Phase 5 evidence. "
                        f"[{origin}]",
                    )
            elif cls == OUT_OF_SCOPE:
                oos_hits += 1
                sev = (
                    "ERROR"
                    if mode == "final-acceptance"
                    else ("WARN" if mode == "qualification" else "INFO")
                )
                add(
                    sev,
                    "P5-FROZEN-05",
                    cls_path,
                    f"OUT_OF_SCOPE non-authority path changed ({status}, "
                    f"source={origin}); not a Phase 5 code change. "
                    "Keep such changes out of Phase 5 commits.",
                )

    if frozen_hits == 0:
        findings.append(
            Finding(
                "PASS",
                "P5-FROZEN-01",
                "",
                f"No FROZEN surface changes (including new files inside frozen "
                f"paths) detected relative to {baseline}.",
            )
        )
    if shared_hits == 0:
        findings.append(
            Finding(
                "PASS",
                "P5-FROZEN-03",
                "",
                f"No SHARED_READ_ONLY surface changes detected relative to {baseline}.",
            )
        )
    if unknown_hits == 0:
        findings.append(
            Finding(
                "PASS",
                "P5-FROZEN-04",
                "",
                "No UNKNOWN-classified changed paths detected.",
            )
        )
    if allowed_hits == 0:
        findings.append(
            Finding(
                "PASS",
                "P5-FROZEN-06",
                "",
                "No Phase 5 allowed-surface changes in this review run.",
            )
        )
    findings.append(
        Finding(
            "INFO",
            "P5-FROZEN-08",
            "",
            "Dirty workspace classification: "
            f"FROZEN dirty={frozen_hits}, SHARED_READ_ONLY dirty={shared_hits}, "
            f"UNKNOWN dirty={unknown_hits}, PHASE5 dirty={allowed_hits}, "
            f"OUT_OF_SCOPE dirty={oos_hits}.",
        )
    )
    return findings


def scan_source_boundaries(files: Sequence[Path], root: Path) -> list[Finding]:
    """Heuristic Phase 5 boundary checks. They surface risk; they are not proof.

    Static authority/future-leakage scans apply to RUNTIME sources only.
    Test/regression sources (is_test_file) exercise runtime behavior — including
    adversarial isolation attempts and outcome computation — and are validated
    by pytest, not by path-name heuristics. A test_shadow_*.py that imports an
    outcome module must not produce a decision-time P5-STATIC-03 ERROR.
    """

    findings: list[Finding] = []
    phase5_files = [path for path in files if phase5_relevant(relpath(path, root))]
    phase5_py = [path for path in phase5_files if path.suffix.lower() == ".py"]

    alt_authority_re = re.compile(
        r"^\s*def\s+(decide|make_decision|finalize_target|canonical_decision|"
        r"generate_(?:buy|sell)_signal|execute_trade|place_order)\s*\(",
        re.IGNORECASE | re.MULTILINE,
    )
    production_import_re = re.compile(
        r"^\s*(?:from\s+[^\n]*(?:broker|order_router|execution_adapter|production)|"
        r"import\s+[^\n]*(?:broker|order_router|execution_adapter|production))",
        re.IGNORECASE | re.MULTILINE,
    )
    outcome_import_re = re.compile(
        r"^\s*(?:from\s+[^\n]*(?:outcome|observation)|import\s+[^\n]*(?:outcome|observation))",
        re.IGNORECASE | re.MULTILINE,
    )
    direct_authority_call_re = re.compile(
        r"\b(finalize_target|permission(?:_authority)?\.(?:set|update|grant)|"
        r"fsm\.(?:transition|set_state)|ledger\.(?:append|write|insert|update))\s*\(",
        re.IGNORECASE,
    )
    canonical_eval_re = re.compile(
        r"(?:decision(?:\.engine)?\.evaluate\s*\(|canonical.*evaluate\s*\(|"
        r"^\s*from\s+[^\n]*decision(?:\.engine|_engine)\s+import\s+[^\n]*\bevaluate\b)",
        re.IGNORECASE | re.MULTILINE,
    )
    monkeypatch_re = re.compile(
        r"\b(monkeypatch|patch\.object|setattr)\b",
        re.IGNORECASE,
    )
    auto_promotion_re = re.compile(
        r"\b(AUTO_PROMOTED|auto_promot(?:e|ion)|PROMOTED_TO_PHASE6|"
        r"start_phase6|enter_phase6|advance_to_phase6)\b",
        re.IGNORECASE,
    )
    hardcoded_human_approval_re = re.compile(
        r"\b(human_approval|human_approved|approved_by_human)\s*=\s*True\b",
        re.IGNORECASE,
    )
    direct_now_re = re.compile(
        r"\b(?:datetime\.)?now\s*\(|\bdatetime\.now\s*\(",
        re.IGNORECASE,
    )
    random_re = re.compile(r"\b(random|numpy\.random|np\.random)\b", re.IGNORECASE)
    seed_re = re.compile(r"\b(seed|random_state|rng)\b", re.IGNORECASE)
    silent_except_re = re.compile(
        r"except(?:\s+Exception)?\s*:\s*(?:\n\s*)?pass\b",
        re.IGNORECASE,
    )

    shadow_files_seen = 0
    shadow_canonical_eval_seen = False

    for path in phase5_py:
        rel = relpath(path, root)
        low = "/" + rel.lower().replace("\\", "/")
        # Review/merge tooling contains governance vocabulary by design and must
        # not be mistaken for runtime Phase 5 implementation. It is still merged
        # into the artifact when selected; only runtime-boundary scanning skips it.
        if "/tools/review/" in low or low.endswith("/merge_project_for_phase5_review.py"):
            continue
        try:
            text = read_text(path)
        except Exception as exc:
            findings.append(
                Finding("WARN", "P5-STATIC-00", rel, f"Could not scan text: {exc}")
            )
            continue
        if is_test_file(rel):
            continue

        is_shadow = "/shadow/" in low or "shadow_" in low or "shadow_runtime" in low
        is_aging = "evidence_aging" in low or "freshness" in low or "evidence_age" in low
        is_promotion = "/promotion/" in low or "promotion_" in low or "qualification" in low

        if is_shadow:
            shadow_files_seen += 1
            if canonical_eval_re.search(text):
                shadow_canonical_eval_seen = True

            m = alt_authority_re.search(text)
            if m:
                findings.append(
                    Finding(
                        "WARN",
                        "P5-STATIC-01",
                        rel,
                        f"Possible duplicate/alternate authority function '{m.group(1)}' in Shadow surface. "
                        "Verify Shadow only invokes the approved canonical evaluation surface.",
                    )
                )

            if production_import_re.search(text):
                findings.append(
                    Finding(
                        "ERROR",
                        "P5-STATIC-02",
                        rel,
                        "Shadow surface imports a production/broker/order/execution-adapter namespace. "
                        "Shadow must have no production action path.",
                    )
                )

            if outcome_import_re.search(text):
                findings.append(
                    Finding(
                        "ERROR",
                        "P5-STATIC-03",
                        rel,
                        "Shadow decision-time surface imports outcome/observation code. "
                        "Review for future leakage; outcome must remain post-decision.",
                    )
                )

            m = direct_authority_call_re.search(text)
            if m:
                findings.append(
                    Finding(
                        "ERROR",
                        "P5-STATIC-04",
                        rel,
                        f"Shadow surface appears to directly call/mutate authority operation '{m.group(1)}'. "
                        "Use canonical evaluation as read/evaluate path; do not mutate Authority/Ledger.",
                    )
                )

            if monkeypatch_re.search(text):
                findings.append(
                    Finding(
                        "WARN",
                        "P5-STATIC-05",
                        rel,
                        "Monkeypatch/setattr behavior detected in Shadow code. Verify no shared mutable "
                        "state or runtime Authority override is possible.",
                    )
                )

        if is_aging and direct_now_re.search(text):
            findings.append(
                Finding(
                    "WARN",
                    "P5-STATIC-06",
                    rel,
                    "Direct wall-clock now() detected in Evidence Aging code. Prefer an injectable/deterministic clock.",
                )
            )

        if is_promotion:
            if auto_promotion_re.search(text):
                findings.append(
                    Finding(
                        "BLOCKER",
                        "P5-STATIC-07",
                        rel,
                        "Automatic Phase 6 promotion vocabulary/path detected. Machine gate may only qualify for Human review.",
                    )
                )
            if hardcoded_human_approval_re.search(text):
                findings.append(
                    Finding(
                        "BLOCKER",
                        "P5-STATIC-08",
                        rel,
                        "Hard-coded Human approval=True detected. Human promotion authority must come from an explicit review artifact/action.",
                    )
                )

        if random_re.search(text) and not seed_re.search(text):
            findings.append(
                Finding(
                    "WARN",
                    "P5-STATIC-09",
                    rel,
                    "Randomness detected without obvious seed/random_state/RNG binding; review replay determinism.",
                )
            )

        if silent_except_re.search(text):
            findings.append(
                Finding(
                    "WARN",
                    "P5-STATIC-10",
                    rel,
                    "Silent 'except: pass' pattern detected. Phase 5 forbids silent failure for evidence/divergence/replay/incidents.",
                )
            )

    # Scan only machine promotion-result artifacts for forbidden auto-promotion
    # status. Specifications/documentation legitimately discuss prohibited terms.
    promotion_artifact_names = {
        "promotion_gate_result.json",
        "phase5_acceptance_summary.json",
    }
    for path in phase5_files:
        if path.name.lower() not in promotion_artifact_names:
            continue
        rel = relpath(path, root)
        try:
            text = read_text(path)
        except Exception:
            continue
        if auto_promotion_re.search(text):
            findings.append(
                Finding(
                    "ERROR",
                    "P5-STATIC-11",
                    rel,
                    "Promotion result artifact contains automatic Phase 6 promotion status/path. "
                    "Machine output must stop at QUALIFIED_FOR_HUMAN_REVIEW.",
                )
            )

    if shadow_files_seen:
        if shadow_canonical_eval_seen:
            findings.append(
                Finding(
                    "PASS",
                    "P5-STATIC-12",
                    "",
                    "Approved/canonical evaluation call detected in Shadow surface.",
                )
            )
        else:
            findings.append(
                Finding(
                    "WARN",
                    "P5-STATIC-12",
                    "",
                    "Shadow files detected but no obvious canonical evaluation call found. "
                    "Verify Shadow does not duplicate the decision engine.",
                )
            )

    if not any(f.severity in {"WARN", "ERROR", "BLOCKER"} for f in findings):
        findings.append(
            Finding(
                "PASS",
                "P5-STATIC-99",
                "",
                "No heuristic Shadow/Authority/Future-Leakage/Promotion warnings detected.",
            )
        )
    return findings


def discover_test_roots(root: Path) -> list[str]:
    """Discover actual QCFP-MTF test roots (repository-aware)."""
    roots: list[str] = []
    for rel in ("Core/QCFP_MTF/tests",):
        if (root / rel).exists():
            roots.append(rel)
    return roots


def find_pytest_targets(root: Path, scope: str) -> tuple[list[str], str]:
    """Discover pytest targets for the requested scope.

    Returns (targets, note). An empty target list is a discovery failure, not
    a pytest return code; callers must report discovery separately.
    """
    targets: list[str] = []
    base = root / "Core" / "QCFP_MTF" / "tests"
    base_rel = "Core/QCFP_MTF/tests"

    if scope == "full":
        roots = discover_test_roots(root)
        if not roots:
            return (
                [],
                "No QCFP-MTF test root discovered (expected "
                "Core/QCFP_MTF/tests). Full pytest cannot run.",
            )
        return roots, f"full scope -> {roots}"

    def add_rel(path: Path) -> None:
        rp = relpath(path, root)
        if rp not in targets:
            targets.append(rp)

    phase5_dir = base / "test_phase5"
    if phase5_dir.exists():
        add_rel(phase5_dir)
    if base.exists():
        for path in sorted(base.rglob("test_*phase5*.py")):
            add_rel(path)
        for path in sorted(base.rglob("*_phase5*.py")):
            add_rel(path)

    if scope == "targeted":
        for rel in (
            "Core/QCFP_MTF/tests/test_decision",
            "Core/QCFP_MTF/tests/test_governance",
            "Core/QCFP_MTF/tests/test_replay",
            "Core/QCFP_MTF/tests/test_safety",
        ):
            if (root / rel).exists() and rel not in targets:
                targets.append(rel)
        if base.exists():
            # Shadow regressions across the QCFP test tree.
            for path in sorted(base.rglob("test_*shadow*.py")):
                add_rel(path)
            research_dir = base / "test_research"
            if research_dir.exists():
                for pattern in ("*promotion*.py", "*outcome*.py"):
                    for path in sorted(research_dir.rglob(pattern)):
                        add_rel(path)

    note = (
        f"{scope} scope -> {len(targets)} target(s): "
        f"{targets or ['<none>']}"
    )
    return targets, note


def run_pytest(
    root: Path,
    scope: str,
    extra_args: Sequence[str],
) -> tuple[int | None, str, list[str], bool, str]:
    """Run pytest with discovered targets.

    Returns (rc_or_None, output, targets, executed, discovery_status).
    rc is None when pytest was never executed because discovery failed; the
    caller must never fabricate a pytest return code such as rc=5.
    """
    targets, note = find_pytest_targets(root, scope)
    cmd = [sys.executable, "-m", "pytest", "-q"]
    if not targets:
        return (
            None,
            "No pytest targets discovered; pytest was not executed. " + note,
            [],
            False,
            "NO_TARGETS",
        )
    cmd.extend(targets)
    if scope == "full":
        for entry in GOVERNED_DESELECTIONS:
            node = entry["node"]
            file_part = node.split("::", 1)[0]
            if (root / file_part).exists():
                cmd.extend(["--deselect", node])
    cmd.extend(extra_args)
    rc, out = run(cmd, root, timeout=3600)
    return rc, out, targets, True, "TARGETS_FOUND"


def parse_pytest_counts(output: str) -> dict[str, int | None]:
    result: dict[str, int | None] = {
        "passed": None,
        "failed": None,
        "errors": None,
        "skipped": None,
    }
    patterns = {
        "passed": r"(?P<n>\d+)\s+passed",
        "failed": r"(?P<n>\d+)\s+failed",
        "errors": r"(?P<n>\d+)\s+errors?",
        "skipped": r"(?P<n>\d+)\s+skipped",
    }
    for key, pattern in patterns.items():
        matches = list(re.finditer(pattern, output, re.IGNORECASE))
        if matches:
            result[key] = int(matches[-1].group("n"))
    return result


def line_numbered(text: str) -> str:
    lines = text.splitlines()
    width = max(4, len(str(len(lines))))
    return "\n".join(f"{i:>{width}} | {line}" for i, line in enumerate(lines, 1))


def summarize_findings(findings: Sequence[Finding]) -> dict[str, int]:
    result: dict[str, int] = {}
    for finding in findings:
        result[finding.severity] = result.get(finding.severity, 0) + 1
    return result


def render_git_section(root: Path, baseline: str) -> str:
    if not git_available(root):
        return "Git repository: NOT DETECTED\n"

    branch = git_text(root, "branch", "--show-current") or "<detached>"
    head = git_text(root, "rev-parse", "HEAD")
    status = git_text(root, "status", "--short") or "<clean>"
    baseline_ok = git_commit_exists(root, baseline)

    if baseline_ok:
        baseline_full = git_text(root, "rev-parse", baseline)
        ancestor = git_is_ancestor(root, baseline, "HEAD")
        merge_base = git_text(root, "merge-base", baseline, "HEAD")
        diff_stat = git_text(root, "diff", "--stat", f"{baseline}...HEAD") or "<no committed diff>"
        name_status = git_text(
            root, "diff", "--name-status", "--find-renames", f"{baseline}...HEAD"
        ) or "<no committed diff>"
    else:
        baseline_full = "<not found>"
        ancestor = False
        merge_base = "<unavailable>"
        diff_stat = "<unavailable>"
        name_status = "<unavailable>"

    worktree_stat = git_text(root, "diff", "--stat") or "<no unstaged diff>"
    staged_stat = git_text(root, "diff", "--cached", "--stat") or "<no staged diff>"

    return "\n".join(
        [
            f"Branch:               {branch}",
            f"HEAD:                 {head}",
            f"Baseline:             {baseline} -> {baseline_full}",
            f"Baseline is ancestor: {ancestor}",
            f"Merge base:           {merge_base}",
            "",
            "Working tree:",
            status,
            "",
            f"Committed diff vs {baseline}:",
            diff_stat,
            "",
            "Committed name/status:",
            name_status,
            "",
            "Staged diff:",
            staged_stat,
            "",
            "Unstaged diff:",
            worktree_stat,
        ]
    )


def render_frozen_change_section(
    changes: Sequence[GitChange],
    root: Path,
    baseline: str,
    manifest: FrozenSurfaceManifest | None,
) -> str:
    if not git_available(root) or not git_commit_exists(root, baseline):
        return "Frozen diff unavailable because Git/baseline verification failed."
    if manifest is None:
        return (
            "Frozen surface classification unavailable because the manifest "
            f"({DEFAULT_MANIFEST_REL}) could not be loaded."
        )

    rows: list[str] = []
    seen: set[str] = set()
    for change in changes:
        rel = change.path.replace("\\", "/")
        old_rel = (change.old_path or rel).replace("\\", "/")
        for cls_path in (rel, old_rel):
            if cls_path in seen:
                continue
            seen.add(cls_path)
            cls = classify_phase5_path(cls_path, manifest)
            subclass = frozen_subclass(cls_path) if cls == FROZEN else ""
            old_info = f" old={change.old_path}" if change.old_path else ""
            rows.append(
                f"{cls:<18} {subclass:<18} status={change.status:<4} "
                f"source={change.source:<9} path={cls_path}{old_info}"
            )
    if not rows:
        return "No changed paths detected against the frozen surface manifest."
    return "\n".join(rows)


def build_manifest(files: Sequence[Path], root: Path) -> list[dict[str, object]]:
    manifest: list[dict[str, object]] = []
    for path in files:
        try:
            manifest.append(
                {
                    "path": relpath(path, root),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
        except OSError as exc:
            manifest.append(
                {
                    "path": str(path),
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

    output = (
        args.output.expanduser()
        if args.output
        else root
        / "Merged_Code"
        / f"merged_QCFP_MTF_phase5_{args.mode}_review.txt"
    )
    if not output.is_absolute():
        output = (root / output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("QCFP-MTF PHASE 5 REVIEW TOOL")
    print("=" * 80)
    print(f"Mode:         {args.mode}")
    print(f"Project root: {root}")
    print(f"Baseline:     {args.baseline}")
    print(f"Manifest:     {DEFAULT_MANIFEST_REL}")
    print(f"Scope:        {args.scope}")
    print(f"Output:       {output}")
    print("=" * 80)

    committed_changes = parse_committed_changes(root, args.baseline)
    worktree_changes = parse_worktree_changes(root)
    untracked_changes = [
        GitChange(status="U", path=rel, source="untracked")
        for rel in current_untracked_files(root)
    ]
    all_changes = combine_changes(
        committed_changes, worktree_changes, untracked_changes
    )

    findings: list[Finding] = []
    surface_manifest, manifest_error = load_frozen_surface_manifest(root)
    if manifest_error:
        findings.append(
            Finding(
                "ERROR",
                "P5-FROZEN-00",
                DEFAULT_MANIFEST_REL,
                manifest_error,
            )
        )

    if not args.skip_git_baseline_validation:
        findings.extend(validate_git_baseline(root, args.baseline, args.mode))

    findings.extend(
        enforce_frozen_surface(
            root, args.baseline, all_changes, args.mode, surface_manifest
        )
    )

    if not args.skip_structure_validation:
        findings.extend(validate_structure(root, args.mode))

    files = collect_review_files(
        root=root,
        baseline=args.baseline,
        scope=args.scope,
        max_file_bytes=args.max_file_bytes,
    )

    # Never self-include the output if it sits outside the normal excluded dir.
    files = [path for path in files if path.resolve() != output.resolve()]

    if not args.skip_static_boundary_validation:
        findings.extend(scan_source_boundaries(files, root))

    pytest_rc: int | None = None
    pytest_out = ""
    pytest_targets: list[str] = []
    pytest_counts: dict[str, int | None] = {
        "passed": None,
        "failed": None,
        "errors": None,
        "skipped": None,
    }
    pytest_executed = False
    pytest_discovery_status = ""
    if args.run_pytest:
        print("Running pytest...")
        (
            pytest_rc,
            pytest_out,
            pytest_targets,
            pytest_executed,
            pytest_discovery_status,
        ) = run_pytest(
            root, args.pytest_scope, args.pytest_extra_arg
        )
        if pytest_executed:
            pytest_counts = parse_pytest_counts(pytest_out)
            sev = "PASS" if pytest_rc == 0 else "ERROR"
            findings.append(
                Finding(
                    sev,
                    "P5-PYTEST-01",
                    "",
                    f"pytest return code = {pytest_rc}; scope={args.pytest_scope}; "
                    f"discovery={pytest_discovery_status}; "
                    f"targets={pytest_targets or ['<full suite>']}; "
                    f"counts={pytest_counts}",
                )
            )
        else:
            sev = (
                "ERROR"
                if args.mode in {"qualification", "final-acceptance"}
                else "WARN"
            )
            findings.append(
                Finding(
                    sev,
                    "P5-PYTEST-02",
                    "",
                    "pytest was not executed because no targets were "
                    f"discovered (discovery_status={pytest_discovery_status}). "
                    f"{pytest_out}",
                )
            )
    elif args.mode in {"qualification", "final-acceptance"}:
        findings.append(
            Finding(
                "ERROR",
                "P5-PYTEST-01",
                "",
                "Qualification/final-acceptance review requires --run-pytest so test evidence is bound into the bundle.",
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
                "QCFP-MTF PHASE 5 SHADOW OPERATION / PROMOTION QUALIFICATION REVIEW BUNDLE",
                f"Tool version:            {TOOL_VERSION}",
                f"Generated at:            {now.isoformat()}",
                f"Project root:            {root}",
                f"Mode:                    {args.mode}",
                f"Frozen baseline:         {args.baseline}",
                f"Review scope:            {args.scope}",
                f"Files merged:            {len(files)}",
                f"Manifest SHA256:         {manifest_hash}",
                "",
                "GOVERNING RULES:",
                "Observe != Control",
                "Shadow != Authority",
                "Outcome != Retroactive Decision",
                "Qualification != Promotion",
                "Automation != Human Approval",
                "",
                "STATIC CHECK NOTE:",
                "Heuristic checks are review aids. PASS does not prove semantic correctness; "
                "WARN/ERROR patterns still require contextual review.",
            ]
        )
    )

    parts.append(banner("1. GIT / SOURCE IDENTITY"))
    parts.append(render_git_section(root, args.baseline))

    parts.append(banner("2. FROZEN SURFACE CHANGE REVIEW"))
    parts.append(
        render_frozen_change_section(
            all_changes, root, args.baseline, surface_manifest
        )
    )

    parts.append(banner("3. PHASE 5 PRE-REVIEW FINDINGS"))
    counts_line = " | ".join(
        f"{key}={counts.get(key, 0)}"
        for key in ("PASS", "INFO", "WARN", "ERROR", "BLOCKER")
    )
    parts.append(counts_line)
    parts.append("")
    for finding in findings:
        parts.append(finding.render())

    parts.append(banner("4. PYTEST"))
    if args.run_pytest:
        parts.append(
            f"pytest scope: {args.pytest_scope}\n"
            f"pytest executed: {pytest_executed}\n"
            f"pytest discovery: {pytest_discovery_status}\n"
            f"pytest targets: {pytest_targets or ['<full suite>']}\n"
            f"pytest return code: {pytest_rc}\n"
            f"pytest parsed counts: {pytest_counts}\n\n"
            f"{pytest_out or '<no output>'}"
        )
    else:
        parts.append(
            "NOT RUN. Re-run with --run-pytest to bind test output into this review bundle. "
            "qualification/final-acceptance mode treats this as an ERROR."
        )

    parts.append(banner("5. FILE MANIFEST"))
    parts.append(
        json.dumps(
            {
                "tool_version": TOOL_VERSION,
                "phase": 5,
                "baseline": args.baseline,
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

    parts.append(banner("6. MERGED REVIEW CONTENT"))
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

    parts.append(banner("7. REVIEW FOOTER"))
    parts.append(
        "\n".join(
            [
                f"Manifest SHA256: {manifest_hash}",
                f"Finding counts: {counts_line}",
                f"pytest rc: {pytest_rc if pytest_rc is not None else '<not run>'}",
                "",
                "Suggested Phase 5 review order:",
                "1) BLOCKER / ERROR findings",
                "2) Phase 4 frozen baseline ancestry + Frozen Surface diff",
                "3) Shadow Runtime identity and storage separation",
                "4) Shadow isolation / no canonical mutation / no production path",
                "5) Canonical-vs-Shadow Divergence taxonomy and replayability",
                "6) Decision -> Outcome linkage and future-leakage controls",
                "7) Evidence Aging / freshness policy and deterministic clock",
                "8) Failure / Incident taxonomy, severity, lifecycle and blocking rules",
                "9) Promotion Gate hard gates; no aggregate-score authority",
                "10) Runtime/decision/outcome/regime coverage sufficiency",
                "11) Changed-file coverage + evidence bundle completeness",
                "12) Human approval boundary (machine qualification must not auto-promote)",
                "",
                "This review tool does NOT approve Phase 5, create a frozen Git tag, or start Phase 6.",
            ]
        )
    )

    output.write_text("\n".join(parts), encoding="utf-8")

    for finding in findings:
        if finding.severity in {"BLOCKER", "ERROR", "WARN"}:
            print(finding.render())

    print("-" * 80)
    print(f"Merged {len(files)} review files")
    print(f"Manifest SHA256: {manifest_hash}")
    print(f"Review bundle written: {output}")

    has_blocking_findings = any(
        finding.severity in {"BLOCKER", "ERROR"} for finding in findings
    )
    pytest_failed = args.run_pytest and pytest_executed and pytest_rc != 0
    effective_strict = args.strict or args.mode in {"qualification", "final-acceptance"}

    if pytest_failed:
        print("RESULT: FAIL (pytest)")
        return 1
    if effective_strict and has_blocking_findings:
        print("RESULT: FAIL (Phase 5 review gate)")
        return 2

    if has_blocking_findings:
        print("RESULT: REVIEW REQUIRED (blocking findings present; use --strict to fail exit code)")
    elif args.mode == "qualification":
        print("RESULT: QUALIFICATION REVIEW BUNDLE CREATED")
        print("NOTE: This does not equal Human promotion approval or PHASE5_PASS.")
    elif args.mode == "final-acceptance":
        print("RESULT: FINAL ACCEPTANCE REVIEW BUNDLE CREATED")
        print("NOTE: Human must still verify the bundle before any freeze tag is created.")
    else:
        print("RESULT: DEVELOPMENT REVIEW BUNDLE CREATED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
