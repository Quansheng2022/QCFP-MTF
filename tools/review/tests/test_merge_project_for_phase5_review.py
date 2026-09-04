# coding: utf-8
"""Phase 5 Review Tool 自身回归测试（FIX-01/03/04 + FIX-08 seed）。

覆盖：
    * Manifest 加载与统一路径分类（FROZEN / SHARED_READ_ONLY /
      PHASE5_ALLOWED / OUT_OF_SCOPE / UNKNOWN）
    * 新文件也必须分类（禁止在 Frozen / Shared / Unknown 路径内新增文件）
    * Frozen Evidence（audit/phase1|3|4、audit/baseline）修改 → BLOCKER
    * pytest 目标发现（Core/QCFP_MTF/tests）
    * 无目标时不伪造 pytest rc=5
    * 静态扫描区分 runtime Shadow 与测试文件

原则：只测 Review Tool 本身；不修改、不依赖业务模块语义。
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TOOLS_REVIEW = PROJECT_ROOT / "tools" / "review"
if str(TOOLS_REVIEW) not in sys.path:
    sys.path.insert(0, str(TOOLS_REVIEW))

import merge_project_for_phase5_review as rv  # noqa: E402


def _manifest():
    manifest, err = rv.load_frozen_surface_manifest(PROJECT_ROOT)
    assert manifest is not None, err
    return manifest


def _chg(status: str, path: str, source: str = "staged",
         old_path: str | None = None) -> rv.GitChange:
    return rv.GitChange(status=status, path=path, old_path=old_path,
                        source=source)


def _enforce(changes, monkeypatch, existed: dict[str, bool] | None = None):
    """Run enforcement with git subprocess stubbed for determinism."""
    monkeypatch.setattr(rv, "git_available", lambda root: True)
    monkeypatch.setattr(rv, "git_commit_exists", lambda root, ref: True)
    mapping = dict(existed or {})

    def _existed(root, baseline, rel):
        return mapping.get(rel, True)

    monkeypatch.setattr(rv, "git_file_existed_at", _existed)
    return rv.enforce_frozen_surface(
        PROJECT_ROOT, "qcfp-mtf-phase4-frozen", changes,
        "development", _manifest(),
    )


def _severities(findings):
    return {f.code: f.severity for f in findings}


def test_manifest_loads_and_declares_required_sections():
    manifest = _manifest()
    assert manifest.frozen
    assert manifest.shared_read_only
    assert manifest.phase5_allowed
    assert manifest.out_of_scope
    assert manifest.source_rel == rv.DEFAULT_MANIFEST_REL


def test_path_classification_frozen_examples():
    m = _manifest()
    for rel in (
        "audit/phase1/phase1_acceptance.json",
        "audit/phase3/phase3_acceptance.json",
        "audit/phase4/phase4_acceptance.json",
        "audit/baseline/governance_baseline.json",
        "Core/QCFP_MTF/decision/engine.py",
        "Core/QCFP_MTF/governance/phase4.py",
        "Core/QCFP_MTF/wave/alternate.py",
    ):
        assert rv.classify_phase5_path(rel, m) == rv.FROZEN, rel


def test_path_classification_shared_read_only():
    m = _manifest()
    for rel in (
        "Core/QCFP_MTF/decision/alternate_engine.py",
        "Core/QCFP_MTF/common/paths.py",
        "Core/QCFP_MTF/execution/broker_adapter.py",
    ):
        assert rv.classify_phase5_path(rel, m) == rv.SHARED_READ_ONLY, rel


def test_path_classification_phase5_allowed():
    m = _manifest()
    for rel in (
        "Core/QCFP_MTF/phase5/contracts.py",
        "Core/QCFP_MTF/tests/test_phase5/test_contracts.py",
        "Core/QCFP_MTF/scripts/phase5_runner.py",
        "audit/phase5/frozen_baseline_identity.json",
        "tools/review/merge_project_for_phase5_review.py",
        "tools/review/tests/test_merge_project_for_phase5_review.py",
    ):
        assert rv.classify_phase5_path(rel, m) == rv.PHASE5_ALLOWED, rel


def test_path_classification_out_of_scope_and_unknown():
    m = _manifest()
    for rel in (
        "Prompt/Prompt_Daily.txt",
        "Report/QCFP_MTF/audit/x.json",
        "Core/Daily/some_script.py",
        "tools/review/merge_project_for_phase4_review_v3.py",
    ):
        assert rv.classify_phase5_path(rel, m) == rv.OUT_OF_SCOPE, rel
    assert rv.classify_phase5_path("unrelated/new_engine.py", m) == rv.UNKNOWN


def test_frozen_subclass_evidence_vs_authority():
    assert rv.frozen_subclass(
        "audit/phase1/phase1_acceptance.json") == rv.FROZEN_EVIDENCE
    assert rv.frozen_subclass(
        "Core/QCFP_MTF/decision/engine.py") == rv.FROZEN_AUTHORITY


def test_frozen_existing_file_modified_blocker(monkeypatch):
    findings = _enforce(
        [_chg("M", "audit/phase1/phase1_acceptance.json")], monkeypatch)
    assert _severities(findings)["P5-FROZEN-01"] == "BLOCKER"


def test_frozen_existing_file_deleted_blocker(monkeypatch):
    findings = _enforce(
        [_chg("D", "audit/phase3/phase3_acceptance.json")], monkeypatch)
    assert _severities(findings)["P5-FROZEN-01"] == "BLOCKER"


def test_frozen_existing_file_renamed_blocker(monkeypatch):
    findings = _enforce(
        [
            _chg(
                "R",
                "Core/QCFP_MTF/decision/engine_backup.py",
                old_path="Core/QCFP_MTF/decision/engine.py",
            )
        ],
        monkeypatch,
    )
    assert _severities(findings)["P5-FROZEN-01"] == "BLOCKER"


def test_frozen_new_file_blocker(monkeypatch):
    # New file inside a FROZEN path is a BLOCKER even though it did not exist
    # at the baseline.
    findings = _enforce(
        [_chg("U", "Core/QCFP_MTF/wave/alternate_wave.py",
              source="untracked")],
        monkeypatch,
        existed={"Core/QCFP_MTF/wave/alternate_wave.py": False},
    )
    assert _severities(findings)["P5-FROZEN-01"] == "BLOCKER"


def test_new_file_inside_shared_read_only_blocker(monkeypatch):
    # decision/alternate_engine.py is a second-Authority risk: new file inside
    # SHARED_READ_ONLY decision/** must block.
    findings = _enforce(
        [_chg("U", "Core/QCFP_MTF/decision/alternate_engine.py",
              source="untracked")],
        monkeypatch,
        existed={"Core/QCFP_MTF/decision/alternate_engine.py": False},
    )
    assert _severities(findings)["P5-FROZEN-03"] == "BLOCKER"


def test_shared_read_only_modified_blocker(monkeypatch):
    findings = _enforce(
        [_chg("M", "Core/QCFP_MTF/common/paths.py")], monkeypatch)
    assert _severities(findings)["P5-FROZEN-03"] == "BLOCKER"


def test_phase5_allowed_new_file_allowed(monkeypatch):
    findings = _enforce(
        [_chg("U", "Core/QCFP_MTF/phase5/contracts.py",
              source="untracked")],
        monkeypatch,
        existed={"Core/QCFP_MTF/phase5/contracts.py": False},
    )
    assert _severities(findings).get("P5-FROZEN-06") in {"PASS", "INFO"}
    assert "BLOCKER" not in {f.severity for f in findings}


def test_phase5_allowed_existing_file_modified_warns(monkeypatch):
    findings = _enforce(
        [_chg("M", "Core/QCFP_MTF/phase5/contracts.py")], monkeypatch)
    assert _severities(findings)["P5-FROZEN-07"] == "WARN"
    assert "BLOCKER" not in {f.severity for f in findings}


def test_unknown_file_blocker(monkeypatch):
    findings = _enforce(
        [_chg("M", "unrelated/new_engine.py")], monkeypatch)
    assert _severities(findings)["P5-FROZEN-04"] == "BLOCKER"


def test_all_audit_evidence_dirs_blocked_when_modified(monkeypatch):
    findings = _enforce(
        [
            _chg("M", "audit/phase1/phase1_acceptance.json"),
            _chg("M", "audit/phase3/frozen_baseline.json"),
            _chg("M", "audit/phase4/phase4_acceptance.json"),
            _chg("M", "audit/baseline/governance_baseline.json"),
        ],
        monkeypatch,
    )
    blockers = [
        f for f in findings
        if f.severity == "BLOCKER" and f.code == "P5-FROZEN-01"
    ]
    assert len(blockers) == 4


def test_manifest_missing_fails_closed(monkeypatch):
    monkeypatch.setattr(rv, "git_available", lambda root: True)
    monkeypatch.setattr(rv, "git_commit_exists", lambda root, ref: True)
    findings = rv.enforce_frozen_surface(
        PROJECT_ROOT, "qcfp-mtf-phase4-frozen", [], "development", None)
    assert any(
        f.code == "P5-FROZEN-00" and f.severity == "ERROR"
        for f in findings
    )


def test_full_pytest_discovery_uses_qcfp_test_root():
    targets, note = rv.find_pytest_targets(PROJECT_ROOT, "full")
    assert targets == ["Core/QCFP_MTF/tests"], note


def test_phase5_pytest_scope_discovers_phase5_suite():
    targets, note = rv.find_pytest_targets(PROJECT_ROOT, "phase5")
    assert targets == ["Core/QCFP_MTF/tests/test_phase5"], note


def test_targeted_pytest_scope_discovers_qcfp_suites():
    targets, _ = rv.find_pytest_targets(PROJECT_ROOT, "targeted")
    joined = "\n".join(targets)
    assert "Core/QCFP_MTF/tests/test_decision" in joined
    assert "Core/QCFP_MTF/tests/test_governance" in joined
    assert "Core/QCFP_MTF/tests/test_safety" in joined
    assert any("shadow" in t.lower() for t in targets)


def test_no_targets_does_not_fabricate_pytest_rc(tmp_path):
    rc, out, targets, executed, status = rv.run_pytest(
        tmp_path, "phase5", [])
    assert rc is None
    assert executed is False
    assert status == "NO_TARGETS"
    assert targets == []
    assert "was not executed" in out


def test_full_pytest_executes_discovered_root(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(cmd, cwd, timeout=3600):
        calls.append(list(cmd))
        return 0, "12 passed"

    monkeypatch.setattr(
        rv, "run", fake_run)
    rc, out, targets, executed, status = rv.run_pytest(
        PROJECT_ROOT, "full", [])
    assert rc == 0
    assert executed is True
    assert status == "TARGETS_FOUND"
    assert targets == ["Core/QCFP_MTF/tests"]
    assert calls
    nodes = [
        entry["node"] for entry in rv.GOVERNED_DESELECTIONS
    ]
    assert calls[0].count("--deselect") == len(nodes)
    for node in nodes:
        assert node in calls[0]


def test_governed_deselection_set_is_exact_and_documented():
    """受控 deselect 集合必须精确、显式、不能静默扩展。"""
    entries = rv.GOVERNED_DESELECTIONS
    assert isinstance(entries, tuple)
    expected_nodes = (
        "Core/QCFP_MTF/tests/test_governance/"
        "test_phase4_evidence_integrity.py::"
        "test_real_runner_builder_judge_pipeline",
        "Core/QCFP_MTF/tests/test_governance/test_phase1.py::"
        "test_phase1_acceptance_pending_baseline",
    )
    actual_nodes = tuple(entry["node"] for entry in entries)
    assert actual_nodes == expected_nodes
    assert len({entry["node"] for entry in entries}) == len(entries)
    for entry in entries:
        assert entry["reason"].strip()
        file_part = entry["node"].split("::", 1)[0]
        assert (PROJECT_ROOT / file_part).exists(), file_part


def test_git_path_commands_disable_quotepath(monkeypatch):
    """非 ASCII 路径必须原样输出，不能出现 C 风格转义（否则分类成 UNKNOWN）。"""
    calls: list[list[str]] = []

    def fake_run(cmd, cwd, timeout=120):
        calls.append(list(cmd))
        return 0, ""

    monkeypatch.setattr(rv, "run", fake_run)
    monkeypatch.setattr(rv, "git_available", lambda root: True)
    monkeypatch.setattr(rv, "git_commit_exists", lambda root, ref: True)
    rv.parse_committed_changes(PROJECT_ROOT, "qcfp-mtf-phase4-frozen")
    rv.parse_worktree_changes(PROJECT_ROOT)
    rv.current_untracked_files(PROJECT_ROOT)
    for cmd in calls:
        assert "-c" in cmd
        assert "core.quotepath=false" in cmd


def test_is_test_file():
    assert rv.is_test_file(
        "Core/QCFP_MTF/tests/test_scripts/test_shadow_universe.py")
    assert rv.is_test_file(
        "Core/QCFP_MTF/tests/test_phase5/test_contracts.py")
    assert rv.is_test_file("tools/review/tests/test_x.py")
    assert not rv.is_test_file("Core/QCFP_MTF/shadow/runtime.py")
    assert not rv.is_test_file(
        "Core/QCFP_MTF/scripts/shadow_universe.py")


def test_runtime_shadow_outcome_import_is_error(tmp_path):
    src = tmp_path / "shadow_runtime.py"
    src.write_text(
        "from outcome_observer import observe\n"
        "def evaluate(inputs):\n"
        "    return observe(inputs)\n",
        encoding="utf-8",
    )
    findings = rv.scan_source_boundaries([src], tmp_path)
    assert any(
        f.code == "P5-STATIC-03" and f.severity == "ERROR"
        for f in findings
    )


def test_shadow_test_outcome_import_is_not_runtime_error(tmp_path):
    tests = tmp_path / "tests"
    tests.mkdir()
    src = tests / "test_shadow_universe.py"
    src.write_text(
        "from QCFP_MTF.scripts.backfill_research_outcomes import "
        "compute_outcome\n",
        encoding="utf-8",
    )
    findings = rv.scan_source_boundaries([src], tmp_path)
    assert not any(
        f.code == "P5-STATIC-03" and f.severity == "ERROR"
        for f in findings
    )
