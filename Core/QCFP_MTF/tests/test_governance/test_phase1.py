# coding: utf-8
"""Phase 1 — Architecture & Specification Freeze 测试

覆盖 P1-FIX-01（Version Authority Gate）、P1-FIX-02（Authority Surface
Hash 进入 Baseline）、P1-FIX-03（Actual Writer 三方证明），以及回归。
"""

import json
from pathlib import Path


def _write(root: Path, rel: str, text: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _fake_project(root: Path) -> None:
    _write(root, "Core/QCFP_MTF/decision/versions.py",
           "MODEL_VERSION = 'QCFP-MTF-TEST'\n")
    _write(root, "Core/QCFP_MTF/ARCHITECTURE.md",
           "# Arch\nversion authority: decision/versions.py\n")
    _write(root, "Core/QCFP_MTF/CANONICAL_SPEC.md", "# Spec\n")
    _write(root, "Core/QCFP_MTF/governance/decision_authority_matrix.yaml",
           "schema: DECISION-AUTHORITY-MATRIX-1\nentries: []\n")
    _write(root, "Core/QCFP_MTF/governance/rule_ownership.py",
           "CANONICAL_RULE_OWNERS = {}\n")
    _write(root, "Core/QCFP_MTF/governance/pwc2_authority_graph.py",
           "def build_authority_graph():\n    return {}\n")
    _write(root, "Core/QCFP_MTF/governance/traceability_manifest.yaml",
           "entries: []\n")
    _write(root, "Core/QCFP_MTF/governance/system_constitution.py",
           "CONSTITUTION_PRINCIPLES = ()\n")
    _write(root, "Core/QCFP_MTF/governance/final_design_principles.py",
           "FINAL_DESIGN_PRINCIPLES = ()\n")


# ---------------------------------------------------------------------------
# P1-FIX-01 — Version Authority Gate（T01~T05）
# ---------------------------------------------------------------------------

def test_t01_historical_doc_exists_with_marker_pass(tmp_path):
    from QCFP_MTF.governance.phase1 import version_authority_record
    root = tmp_path / "proj"
    _fake_project(root)
    _write(root, "Doc/QCFP-MTF 2.2_架构设计.md",
           "# Old\nHistorical Design / Evolution Record\n")
    record = version_authority_record(
        root, historical_docs=["Doc/QCFP-MTF 2.2_架构设计.md"])
    assert record["verdict"] == "VERSION_AUTHORITY_PASS", record
    assert not record["warnings"]


def test_t02_historical_doc_missing_pass_with_warning(tmp_path):
    from QCFP_MTF.governance.phase1 import version_authority_record
    root = tmp_path / "proj"
    _fake_project(root)
    record = version_authority_record(
        root, historical_docs=["Doc/old.md"])
    assert record["verdict"] == "VERSION_AUTHORITY_PASS", record
    assert any("缺失" in w for w in record["warnings"])


def test_t03_historical_doc_old_version_pass_with_warning(tmp_path):
    from QCFP_MTF.governance.phase1 import version_authority_record
    root = tmp_path / "proj"
    _fake_project(root)
    _write(root, "Doc/old.md",
           "# Old\nHistorical Design / Evolution Record\n"
           "MODEL_VERSION = QCFP-MTF-2.1.1\n")
    record = version_authority_record(
        root, historical_docs=["Doc/old.md"])
    assert record["verdict"] == "VERSION_AUTHORITY_PASS", record
    assert any("历史版本号" in w for w in record["warnings"])


def test_t04_versions_py_missing_fail(tmp_path):
    from QCFP_MTF.governance.phase1 import version_authority_record
    root = tmp_path / "proj"
    _write(root, "Core/QCFP_MTF/ARCHITECTURE.md",
           "# Arch\nversion authority: decision/versions.py\n")
    record = version_authority_record(root)
    assert record["verdict"] == "VERSION_AUTHORITY_FAIL"
    assert any("decision/versions.py 不存在" in p
               for p in record["problems"])


def test_t05_architecture_declares_another_authority_fail(tmp_path):
    from QCFP_MTF.governance.phase1 import version_authority_record
    root = tmp_path / "proj"
    _fake_project(root)
    _write(root, "Core/QCFP_MTF/ARCHITECTURE.md",
           "# Arch\nversion authority: my_own_version.py\n")
    record = version_authority_record(root)
    assert record["verdict"] == "VERSION_AUTHORITY_FAIL"
    assert any("未声明 versions authority" in p
               for p in record["problems"])


# ---------------------------------------------------------------------------
# P1-FIX-02 — Authority Surface Hash（T06~T09）
# ---------------------------------------------------------------------------

def _tmp_surface(root: Path) -> list:
    surface = [
        "Core/QCFP_MTF/governance/decision_authority_matrix.yaml",
        "Core/QCFP_MTF/governance/rule_ownership.py",
        "Core/QCFP_MTF/governance/traceability_manifest.yaml",
    ]
    for rel in surface:
        _write(root, rel, f"content of {rel}\n")
    return surface


def test_t06_matrix_tamper_changes_surface_hash(tmp_path):
    from QCFP_MTF.governance.phase1 import phase1_authority_surface_hash
    root = tmp_path / "proj"
    surface = _tmp_surface(root)
    before = phase1_authority_surface_hash(root, surface)
    _write(root, surface[0],
           "PermissionPolicy -> Governance\n")  # 篡改矩阵
    assert phase1_authority_surface_hash(root, surface) != before


def test_t07_rule_ownership_tamper_changes_surface_hash(tmp_path):
    from QCFP_MTF.governance.phase1 import phase1_authority_surface_hash
    root = tmp_path / "proj"
    surface = _tmp_surface(root)
    before = phase1_authority_surface_hash(root, surface)
    _write(root, surface[1], "permission_upper_bound: Governance\n")
    assert phase1_authority_surface_hash(root, surface) != before


def test_t08_traceability_tamper_changes_surface_hash(tmp_path):
    from QCFP_MTF.governance.phase1 import phase1_authority_surface_hash
    root = tmp_path / "proj"
    surface = _tmp_surface(root)
    before = phase1_authority_surface_hash(root, surface)
    _write(root, surface[2], "authority: decision.governance\n")
    assert phase1_authority_surface_hash(root, surface) != before


def test_t09_historical_doc_tamper_does_not_change_surface_hash(tmp_path):
    from QCFP_MTF.governance.phase1 import phase1_authority_surface_hash
    root = tmp_path / "proj"
    surface = _tmp_surface(root)
    before = phase1_authority_surface_hash(root, surface)
    _write(root, "Doc/old.md", "tampered historical doc\n")
    assert phase1_authority_surface_hash(root, surface) == before


def test_baseline_detects_authority_surface_drift():
    from QCFP_MTF.governance.governance_baseline import (
        compute_baseline, verify_baseline,
    )
    b = compute_baseline()
    assert b["phase1_authority_surface_hash"]
    assert verify_baseline(dict(b))["verdict"] == "PASS"
    drifted = dict(b)
    drifted["phase1_authority_surface_hash"] = "deadbeef"
    bad = verify_baseline(drifted)
    assert bad["verdict"] == "BASELINE_CHANGED"
    assert "phase1_authority_surface_hash" in bad["drift"]


# ---------------------------------------------------------------------------
# P1-FIX-03 — Actual Writer Proof（T10~T14）
# ---------------------------------------------------------------------------

def _full_overrides() -> dict:
    return {
        "Permission": ["decision.institutional_permission"],
        "Opportunity": ["wave.canonical"],
        "Lifecycle": ["decision.retail_position_fsm"],
        "Hard Risk": ["decision.hard_exit"],
        "Final Target": ["decision.governance"],
        "Validation": ["governance.validation_certificate"],
        "Historical Fact": ["decision.decision_ledger"],
        "Report": [],
    }


def _base_graph() -> dict:
    return {"nodes": {}, "edges": [], "roots": {}}


def test_t10_synchronized_matrix_rule_forgery_rejected():
    """Matrix + Rule Owner 同时伪造为 Governance，生产代码不变 → 必须 FAIL。"""
    from QCFP_MTF.governance.phase1 import decision_authority_audit
    forged_matrix = {
        "entries": [{
            "domain": "Permission",
            "spec_id": "QCFP-SPEC-AUTH-001",
            "production_owner": "Governance",  # 伪造
        }],
        "rule_id_mapping": {"Permission": "permission_upper_bound"},
    }
    from QCFP_MTF.governance.rule_ownership import CANONICAL_RULE_OWNERS
    # 同时伪造 rule ownership（把 permission 的 owner 改成 Governance）
    original = dict(CANONICAL_RULE_OWNERS)
    CANONICAL_RULE_OWNERS["permission_upper_bound"] = "Governance"
    try:
        result = decision_authority_audit(
            graph=_base_graph(),
            observed_overrides=_full_overrides(),
            matrix=forged_matrix,
        )
    finally:
        CANONICAL_RULE_OWNERS.clear()
        CANONICAL_RULE_OWNERS.update(original)
    assert result["verdict"] == "AUTHORITY_FAIL", result["problems"]
    assert any("AUTHORITY_OWNER_MISMATCH" in p
               for p in result["problems"])


def test_t11_duplicate_writer_rejected():
    from QCFP_MTF.governance.phase1 import decision_authority_audit
    overrides = _full_overrides()
    overrides["Final Target"] = ["decision.governance", "decision.evil"]
    result = decision_authority_audit(
        graph=_base_graph(), observed_overrides=overrides)
    assert result["verdict"] == "AUTHORITY_FAIL"
    assert any("DUPLICATE_WRITER" in p for p in result["problems"])


def test_t12_dead_authority_rejected():
    from QCFP_MTF.governance.phase1 import decision_authority_audit
    overrides = _full_overrides()
    overrides["Permission"] = []
    result = decision_authority_audit(
        graph=_base_graph(), observed_overrides=overrides)
    assert result["verdict"] == "AUTHORITY_FAIL"
    assert result["dead_authorities"] >= 1


def test_t13_report_becomes_decision_writer_rejected():
    from QCFP_MTF.governance.phase1 import decision_authority_audit
    graph = _base_graph()
    graph["nodes"]["report.dss_output"] = {
        "decision_critical": True, "production_reachable": True}
    result = decision_authority_audit(
        graph=graph, observed_overrides=_full_overrides())
    assert result["verdict"] == "AUTHORITY_FAIL"
    assert "report.dss_output" in result["report_decision_writers"]


def test_t14_research_becomes_production_writer_rejected():
    from QCFP_MTF.governance.phase1 import decision_authority_audit
    graph = _base_graph()
    graph["nodes"]["decision.governance"] = {
        "production_reachable": True, "decision_critical": True}
    graph["edges"] = [{
        "source": "research.future_label",
        "target": "decision.governance",
        "type": "IMPORTS"}]
    result = decision_authority_audit(
        graph=graph, observed_overrides=_full_overrides())
    assert result["verdict"] == "AUTHORITY_FAIL"
    assert result["research_production_writers"]


def test_t12b_authority_surface_file_deletion_rejected(tmp_path):
    from QCFP_MTF.governance.phase1 import phase1_authority_surface_hash
    root = tmp_path / "proj"
    surface = _tmp_surface(root)
    (root / surface[0]).unlink()
    import pytest
    with pytest.raises(FileNotFoundError):
        phase1_authority_surface_hash(root, surface)


# ---------------------------------------------------------------------------
# 回归：真实树 Phase 1 Gate
# ---------------------------------------------------------------------------

def test_version_authority_record_real():
    from QCFP_MTF.governance.phase1 import version_authority_record
    record = version_authority_record()
    assert record["verdict"] == "VERSION_AUTHORITY_PASS", record
    assert record["runtime_version_authority"] == \
        "Core/QCFP_MTF/decision/versions.py"


def test_freeze_scope_manifest_complete():
    from QCFP_MTF.governance.phase1 import freeze_scope_check
    result = freeze_scope_check()
    assert result["verdict"] == "FREEZE_SCOPE_PASS", result
    assert not result["missing"]


def test_decision_authority_audit_real_tree():
    from QCFP_MTF.governance.phase1 import decision_authority_audit
    result = decision_authority_audit()
    assert result["verdict"] == "AUTHORITY_OK", result["problems"]
    assert result["duplicate_writers"] == 0
    assert result["unauthorized_writers"] == 0
    assert result["dead_authorities"] == 0
    assert result["owner_mismatches"] == 0
    assert result["report_decision_writers"] == []
    assert result["research_production_writers"] == []
    assert all(row["ok"] for row in result["matrix"])


def test_phase1_acceptance_pending_baseline():
    """修复后：非 baseline Gate 全 PASS；baseline 因旧 Frozen 缺新字段
    报 BASELINE_CHANGED（待 Human Approval 新 Candidate 后恢复 PASS）。"""
    from QCFP_MTF.governance.phase1 import phase1_acceptance
    acceptance = phase1_acceptance()
    gates = acceptance["gates"]
    for name in ("version_authority", "freeze_scope", "canonical_spec",
                 "decision_authority", "traceability"):
        assert gates[name]["pass"], (name, gates[name].get("problems"))
    baseline = gates["baseline"]
    assert baseline["verdict"] in ("BASELINE_PASS", "BASELINE_CHANGED")
    if baseline["verdict"] == "BASELINE_CHANGED":
        assert "phase1_authority_surface_hash" in baseline.get("drift", {})
    assert acceptance["phase1_authority_surface_sha256"]
