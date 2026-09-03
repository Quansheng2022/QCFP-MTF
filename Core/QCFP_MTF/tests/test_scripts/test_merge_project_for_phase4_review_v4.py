# coding: utf-8
"""P1-REV-01：Changed-File Review Coverage（merge v4）测试

DoD:
    changed target text files ⊆ merged review files
    missing_changed_target_files == []
    P4-REVIEW-COVERAGE-01 == PASS
"""

import contextlib
import sys
import tempfile
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_TOOLS_REVIEW = _PROJECT_ROOT / "tools" / "review"
if str(_TOOLS_REVIEW) not in sys.path:
    sys.path.insert(0, str(_TOOLS_REVIEW))

import merge_project_for_phase4_review_v4 as merger  # noqa: E402


def _tmp_workspace() -> tuple:
    """创建临时 project 与 Core/QCFP_MTF target 子树。"""
    d = tempfile.TemporaryDirectory()
    project = Path(d.name)
    target = project / "Core" / "QCFP_MTF"
    target.mkdir(parents=True)
    return d, project, target


@contextlib.contextmanager
def _patch_git(project: Path, changed_rels, untracked=()):
    def fake_changes(root, baseline):
        assert root == project
        return [merger.GitChange("A", rel) for rel in changed_rels]

    def fake_untracked(root):
        assert root == project
        return list(untracked)

    old1, old2 = merger.parse_git_changes, merger.current_untracked_files
    merger.parse_git_changes = fake_changes
    merger.current_untracked_files = fake_untracked
    try:
        yield
    finally:
        merger.parse_git_changes = old1
        merger.current_untracked_files = old2


def test_changed_target_text_file_is_always_merged():
    """phase4.py 无 backtest/ablation/oos 特征，但作为 changed target 必须进 bundle。"""
    d, project, target = _tmp_workspace()
    try:
        changed = [
            "Core/QCFP_MTF/governance/phase4.py",
            "Core/QCFP_MTF/scripts/governance_flow.py",
        ]
        for rel in changed:
            p = project / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("# changed\n", encoding="utf-8")
        with _patch_git(project, changed):
            files = merger.collect_review_files(
                project_root=project,
                target_root=target,
                baseline="cdcab0c",
                scope="phase4",
                max_file_bytes=1_500_000,
            )
        rels = {str(p.relative_to(project)).replace("\\", "/")
                for p in files}
        assert "Core/QCFP_MTF/governance/phase4.py" in rels
        assert "Core/QCFP_MTF/scripts/governance_flow.py" in rels
    finally:
        d.cleanup()


def test_all_changed_target_files_have_review_sections():
    d, project, target = _tmp_workspace()
    try:
        changed = [
            "Core/QCFP_MTF/governance/phase4.py",
            "Core/QCFP_MTF/scripts/governance_flow.py",
            "Core/QCFP_MTF/scripts/phase4_regression_runner.py",
        ]
        for rel in changed:
            p = project / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("x = 1\n", encoding="utf-8")
        with _patch_git(project, changed):
            files = merger.collect_review_files(
                project, target, "cdcab0c", "phase4", 1_500_000)
            merged_rels = {
                str(p.relative_to(project)).replace("\\", "/")
                for p in files}
            coverage = merger.changed_target_records(
                project, target,
                [merger.GitChange("A", r) for r in changed],
                [], merged_rels, 1_500_000)
        assert coverage["changed_target_text_count"] == 3
        assert coverage["merged_changed_target_text_count"] == 3
        assert coverage["missing_changed_target_files"] == []
        for row in coverage["rows"]:
            assert row["kind"] == "text_merged"
            assert row["sha256"]
    finally:
        d.cleanup()


def test_missing_changed_target_file_blocks_acceptance():
    d, project, target = _tmp_workspace()
    try:
        changed = ["Core/QCFP_MTF/governance/phase4.py"]
        (project / changed[0]).parent.mkdir(parents=True, exist_ok=True)
        (project / changed[0]).write_text("x = 1\n", encoding="utf-8")
        coverage = merger.changed_target_records(
            project, target,
            [merger.GitChange("A", r) for r in changed],
            [], set(), 1_500_000)
        dev = merger.coverage_findings(coverage, "development")
        acc = merger.coverage_findings(coverage, "acceptance")
        assert any(f.severity == "ERROR"
                   and f.code == "P4-REVIEW-COVERAGE-01" for f in dev)
        assert any(f.severity == "BLOCKER"
                   and f.code == "P4-REVIEW-COVERAGE-01" for f in acc)
        assert coverage["missing_changed_target_files"] == changed
    finally:
        d.cleanup()


def test_changed_file_outside_target_does_not_pollute_bundle():
    d, project, target = _tmp_workspace()
    try:
        outside = "README.md"
        (project / outside).write_text("readme\n", encoding="utf-8")
        changed_target = "Core/QCFP_MTF/governance/phase4.py"
        (project / changed_target).parent.mkdir(parents=True, exist_ok=True)
        (project / changed_target).write_text("x = 1\n", encoding="utf-8")
        with _patch_git(project, [outside, changed_target]):
            files = merger.collect_review_files(
                project, target, "cdcab0c", "phase4", 1_500_000)
            coverage = merger.changed_target_records(
                project, target,
                [merger.GitChange("A", outside),
                 merger.GitChange("A", changed_target)],
                [], set(), 1_500_000)
        rels = {str(p.relative_to(project)).replace("\\", "/")
                for p in files}
        assert outside not in rels
        rows = {r["rel"] for r in coverage["rows"]}
        assert outside not in rows
        assert changed_target in rows
    finally:
        d.cleanup()


def test_changed_binary_is_manifested_with_explicit_exclusion():
    d, project, target = _tmp_workspace()
    try:
        binary = "Core/QCFP_MTF/data/chart.png"
        p = project / binary
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"\x89PNG\r\n\x1a\n")
        coverage = merger.changed_target_records(
            project, target,
            [merger.GitChange("A", binary)],
            [], set(), 1_500_000)
        findings = merger.coverage_findings(coverage, "acceptance")
        row = coverage["rows"][0]
        assert row["kind"] == "binary"
        assert row["merged"] is False
        assert any(f.severity == "INFO" for f in findings)
        assert binary in coverage["excluded_binary_files"]
    finally:
        d.cleanup()
