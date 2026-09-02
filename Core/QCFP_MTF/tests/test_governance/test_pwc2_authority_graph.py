# coding: utf-8
"""PWC-2 Production Authority Graph + Physical Retirement 测试"""

import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.pwc2_authority_graph import (
    authority_audit, build_authority_graph, convergence_before_after,
    behavioral_authority_audit, behavioral_write_scan,
    logical_detachment, pwc2_definition_of_done, retirement_classify,
    retirement_register, scan_imports)


def _write_tree(root: Path):
    (root / "decision").mkdir(parents=True, exist_ok=True)
    (root / "research").mkdir(parents=True, exist_ok=True)
    (root / "decision" / "engine.py").write_text(
        "from QCFP_MTF.decision.governance import finalize_target\n"
        "from QCFP_MTF.decision.canonical_action import canonical_action\n",
        encoding="utf-8")
    (root / "decision" / "governance.py").write_text(
        "def finalize_target(): return 0\n", encoding="utf-8")
    (root / "decision" / "canonical_action.py").write_text(
        "def canonical_action(): return 'ENTRY'\n", encoding="utf-8")
    (root / "decision" / "permission_policy.py").write_text(
        "def permission_policy_object(): return {}\n", encoding="utf-8")
    (root / "research" / "ablation.py").write_text(
        "def ablate(): return 0\n", encoding="utf-8")


def test_scan_imports():
    edges = scan_imports(
        "from QCFP_MTF.decision.governance import finalize_target\n"
        "from ..decision import engine\n"
        "import QCFP_MTF.decision.ledger\n",
        current_module="decision.engine")
    targets = [t for _, t in edges]
    assert "decision.governance" in targets
    assert "decision.ledger" in targets


def test_behavioral_write_scan():
    src = ("df['final_target'] = 0.2\n"
           "UPDATE qcfp_decision SET final_target=0.2\n"
           "finalize_target(perm, mode, cap)\n")
    writes = behavioral_write_scan(src)
    fields = [w[1] for w in writes]
    assert "final_target" in fields
    assert any(w[0] == "SQL" for w in writes)
    assert any(w[0] == "CALLS" for w in writes)


def test_behavioral_authority_audit(tmp_path2=None):
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _write_tree(root)
        # 给两个模块都写 final_target → 行为级重复权威
        (root / "decision" / "governance.py").write_text(
            "df['final_target'] = 0.2\n", encoding="utf-8")
        (root / "decision" / "engine.py").write_text(
            "from QCFP_MTF.decision.governance import finalize_target\n"
            "df['final_target'] = 0.1\n", encoding="utf-8")
        g = build_authority_graph(root)
        r = behavioral_authority_audit(g)
        assert r["verdict"] == "BEHAVIORAL_DUPLICATE_AUTHORITY"
        assert "duplicate_final_target_authority" in r["duplicates"]


def test_behavioral_audit_skips_research_and_dedup(tmp_path2=None):
    """Sprint A：非 Production 模块不得计为 Authority；
    同一模块内 ASSIGN+CALLS 只计 1 个 owner；非 Owner 写入 →
    UNAUTHORIZED_WRITER。"""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _write_tree(root)
        (root / "decision" / "governance.py").write_text(
            "df['final_target'] = 0.2\n"
            "finalize_target(perm, mode, cap)\n", encoding="utf-8")
        (root / "research" / "ablation.py").write_text(
            "df['final_target'] = 0.9\n", encoding="utf-8")
        g = build_authority_graph(root)
        r = behavioral_authority_audit(g)
        # research.ablation 不可达 → 不计入；governance 是 Owner 且
        # ASSIGN+CALLS 只算一个 owner → 无 duplicate、无 unauthorized
        assert r["verdict"] == "BEHAVIORAL_AUTHORITY_OK"
        assert r["field_writers"]["final_target"] == ["decision.governance"]
        assert r["duplicates"] == {}
        assert r["unauthorized_writers"] == {}


def test_behavioral_audit_unauthorized_writer(tmp_path2=None):
    """Sprint A：非 Owner 模块写入最终字段 → UNAUTHORIZED_WRITER。"""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _write_tree(root)
        (root / "decision" / "governance.py").write_text(
            "df['final_target'] = 0.2\n", encoding="utf-8")
        (root / "decision" / "permission_policy.py").write_text(
            "df['final_target'] = 0.1\n", encoding="utf-8")
        # permission_policy 不 import engine，但位于 decision 包；
        # 手动构造 graph 使两个模块都 reachable
        g = build_authority_graph(root)
        g["nodes"]["decision.permission_policy"]["production_reachable"] = True
        r = behavioral_authority_audit(g)
        assert r["verdict"] == "BEHAVIORAL_DUPLICATE_AUTHORITY"
        assert "unauthorized_final_target_writer" in \
            r["unauthorized_writers"]
        assert r["unauthorized_writers"][
            "unauthorized_final_target_writer"] == [
                "decision.permission_policy"]


def test_build_graph_and_audit():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _write_tree(root)
        g = build_authority_graph(root)
        assert "decision.governance" in g["nodes"]
        assert g["nodes"]["decision.governance"][
            "production_reachable"] is True
        a = authority_audit(g)
        assert isinstance(a["duplicate_authority"], dict)


def test_retirement_classify_and_register():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _write_tree(root)
        g = build_authority_graph(root)
        cls = retirement_classify(g)
        reg = retirement_register(g, cls)
        assert reg["keep"]
        assert cls["classifications"]["decision.governance"][
            "classification"] == "ACTIVE_CORE"


def test_logical_detachment():
    g = {"nodes": {"a": {"production_reachable": True},
                   "b": {"production_reachable": False}}}
    r = logical_detachment(g, ["b"])
    assert r["verdict"] == "DETACHED"
    r2 = logical_detachment(g, ["a"])
    assert r2["verdict"] == "STILL_REACHABLE"


def test_convergence_before_after():
    before = {"production_files": 100, "production_critical_loc": 5000,
              "active_modules": 40, "active_features": 60,
              "executable_decision_paths": 3, "duplicate_authorities": 2,
              "legacy_production_imports": 2, "canonical_coverage": 0.8,
              "replay_coverage": 0.85, "invariant_coverage": 0.8,
              "oos_evidence_quality": 0.7}
    after = dict(before)
    after.update({"production_critical_loc": 4000, "active_features": 45,
                  "executable_decision_paths": 1,
                  "duplicate_authorities": 0,
                  "legacy_production_imports": 0,
                  "canonical_coverage": 0.95, "replay_coverage": 0.95,
                  "invariant_coverage": 0.9, "oos_evidence_quality": 0.85})
    r = convergence_before_after(before, after)
    assert r["verdict"] == "PHYSICAL_CONVERGENCE_PROVEN"
    assert r["hard_down"] is True


def test_convergence_incomplete_when_loc_up():
    before = {"production_critical_loc": 4000, "active_features": 50,
              "executable_decision_paths": 2, "duplicate_authorities": 2,
              "legacy_production_imports": 1, "canonical_coverage": 0.8,
              "replay_coverage": 0.85, "invariant_coverage": 0.8,
              "oos_evidence_quality": 0.7, "production_files": 100,
              "active_modules": 40}
    after = dict(before)
    after["production_critical_loc"] = 5000
    r = convergence_before_after(before, after)
    assert r["verdict"] == "PHYSICAL_CONVERGENCE_INCOMPLETE"


def test_definition_of_done():
    checks = {r: True for r in (
        "graph_from_real_roots", "all_modules_classified",
        "unmapped_production_zero", "canonical_authority_one",
        "permission_authority_one", "final_target_authority_one",
        "validation_authority_one", "wave_taxonomy_one",
        "report_decision_authority_zero",
        "research_production_dependency_zero",
        "legacy_production_dependency_zero",
        "active_but_unwired_zero", "duplicate_authority_zero",
        "retirement_review_complete", "logical_detachment_complete",
        "physical_deletion_complete", "golden_corpus_pass", "replay_pass",
        "canonical_oos_pass", "canonical_stress_pass",
        "failure_injection_pass", "executable_paths_down",
        "active_features_down", "production_loc_down",
        "coverage_not_down")}
    r = pwc2_definition_of_done(checks)
    assert r["verdict"] == "PWC2_CLOSED"
    checks["physical_deletion_complete"] = False
    r2 = pwc2_definition_of_done(checks)
    assert r2["verdict"] == "PWC2_INCOMPLETE"


def test_real_tree_artifacts():
    """真实代码库上跑 PWC-2：五类审计 + 5 个 Artifact 可生成。"""
    from QCFP_MTF.governance.pwc2_authority_graph import pwc2_release_artifacts
    qcfp_root = Path(CORE_DIR) / "QCFP_MTF"
    before = {"production_files": 1, "production_critical_loc": 1,
              "active_modules": 1, "active_features": 1,
              "executable_decision_paths": 3,
              "duplicate_authorities": 2, "legacy_production_imports": 2,
              "canonical_coverage": 0.8, "replay_coverage": 0.85,
              "invariant_coverage": 0.8, "oos_evidence_quality": 0.7}
    after = dict(before)
    after.update({"production_critical_loc": 1, "active_features": 1,
                  "executable_decision_paths": 1,
                  "duplicate_authorities": 0,
                  "legacy_production_imports": 0,
                  "canonical_coverage": 0.95, "replay_coverage": 0.95,
                  "invariant_coverage": 0.9, "oos_evidence_quality": 0.85})
    checks = {r: True for r in (
        "graph_from_real_roots", "all_modules_classified",
        "unmapped_production_zero", "canonical_authority_one",
        "permission_authority_one", "final_target_authority_one",
        "validation_authority_one", "wave_taxonomy_one",
        "report_decision_authority_zero",
        "research_production_dependency_zero",
        "legacy_production_dependency_zero",
        "active_but_unwired_zero", "duplicate_authority_zero",
        "retirement_review_complete", "logical_detachment_complete",
        "physical_deletion_complete", "golden_corpus_pass", "replay_pass",
        "canonical_oos_pass", "canonical_stress_pass",
        "failure_injection_pass", "executable_paths_down",
        "active_features_down", "production_loc_down",
        "coverage_not_down")}
    a = pwc2_release_artifacts(qcfp_root, before, after, checks)
    assert "authority_graph" in a
    assert "retirement_register" in a
    assert "production_manifest" in a
    assert a["production_manifest"]["count"] > 0
