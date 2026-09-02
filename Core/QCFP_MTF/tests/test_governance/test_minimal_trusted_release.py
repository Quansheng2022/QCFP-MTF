# coding: utf-8
"""Minimal Trusted Production Release 12 项测试"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.minimal_trusted_release import (
    AUTHORITY_GATE, FROZEN_PRODUCTION_MANIFEST,
    V9_PRODUCTION_BASELINE_MANIFEST, active_feature_diff,
    convergence_certificate, critical_loc_metrics, definition_of_done_10,
    deletion_invariant, evaluate_mtr, freeze_baseline,
    freeze_mtr_baseline, physical_delete,
    production_feature_manifest_artifact, production_roots,
    regression_evidence, release_gates, removal_candidates,
    retirement_evidence, shrinkage_scoreboard, trust_scoreboard,
    verify_frozen_manifest, verify_unreachable)


def test_freeze_baseline_and_roots():
    b = freeze_baseline({"paths": 3})
    assert b["frozen"] is True
    assert "canonical_engine" in production_roots()["roots"]


def test_removal_candidates():
    audit = {"duplicate_authority": {"FINAL_TARGET": ["a", "b"]},
             "production_orphan": ["c"], "research_leakage": [],
             "governance_island": []}
    classifications = {"classifications": {
        "a": {"classification": "ACTIVE_CORE"},
        "b": {"classification": "ACTIVE_CORE"},
        "c": {"classification": "RESEARCH_ONLY"}}}
    r = removal_candidates(audit, classifications)
    assert r["count"] == 3
    assert "a" in r["candidates"]


def test_retirement_evidence_mandatory_exception():
    candidates = {"candidates": {"Permission": {}, "LegacyX": {}}}
    r = retirement_evidence(
        candidates,
        behavior={"Permission": {"mandatory_governance": True}},
        ablation={"LegacyX": {"ablation_value": 0.0}})
    assert r["evidence"]["Permission"]["decision"] == "KEEP_CONSTITUTIONAL"
    assert r["evidence"]["LegacyX"]["decision"] == "DELETE"
    assert r["delete_candidates"] == ["LegacyX"]


def test_verify_unreachable():
    before = {"nodes": {"x": {"production_reachable": True}}}
    after = {"nodes": {"x": {"production_reachable": False}}}
    r = verify_unreachable(before, after, ["x"])
    assert r["verdict"] == "DETACHED"
    r2 = verify_unreachable(before, before, ["x"])
    assert r2["verdict"] == "STILL_REACHABLE"


def test_physical_delete():
    r = physical_delete(["x"], actual_removed=["x"])
    assert r["verdict"] == "DELETE_COMPLETE"
    r2 = physical_delete(["x"], actual_removed=[])
    assert r2["verdict"] == "DELETE_PENDING"


def test_physical_delete_requires_real_removal():
    """Sprint D：actual_removed=[] 或候选文件仍存在或存在残余引用，
    一律不得宣布 DELETE_COMPLETE。"""
    r = physical_delete(["decision.score_calculator"],
                        actual_removed=[],
                        qcfp_root=Path(CORE_DIR) / "QCFP_MTF")
    assert r["verdict"] == "DELETE_PENDING"
    assert r["retired_removed_count"] == 0
    # 残余引用 → 仍 PENDING
    r2 = physical_delete(["x"], actual_removed=["x"],
                         qcfp_root=Path(CORE_DIR) / "QCFP_MTF",
                         residual_references=[{"file": "a.py",
                                               "module": "x"}])
    assert r2["verdict"] == "DELETE_PENDING"
    assert r2["residual_references"]


def test_score_calculator_physically_deleted():
    """Sprint D：score_calculator 必须真正从磁盘删除。"""
    assert not (Path(CORE_DIR) / "QCFP_MTF" / "decision" /
                "score_calculator.py").exists()
    assert not (Path(CORE_DIR) / "QCFP_MTF" / "tests" /
                "test_decision" / "test_score_calculator.py").exists()


def test_scan_residual_references_real_tree():
    """Sprint D：真实工程扫描退役模块的残余引用。"""
    from QCFP_MTF.governance.minimal_trusted_release import \
        scan_residual_references
    refs = scan_residual_references(
        Path(CORE_DIR) / "QCFP_MTF",
        ["decision.score_calculator"])
    assert refs == []


def test_deletion_invariant():
    before = {"failure_injection_cases": 12, "replay_coverage": 0.96,
              "invariant_checks": 14, "golden_corpus_pass": 1}
    after = dict(before)
    assert deletion_invariant(before, after)["verdict"] == "TRUST_PRESERVED"
    after["replay_coverage"] = 0.80
    assert deletion_invariant(before, after)["verdict"] == "TRUST_REGRESSED"


def _before():
    return {"executable_decision_paths": 3, "active_features": 20,
            "production_critical_loc": 5000, "production_modules": 20,
            "duplicate_authorities": 2, "legacy_production_imports": 2,
            "canonical_golden_pass": 1.0, "replay_coverage": 0.96,
            "invariant_coverage": 0.92, "pit_compliance": 1.0,
            "oos_evidence_grade": "A"}


def _after():
    a = _before()
    a.update({"executable_decision_paths": 1, "active_features": 10,
              "production_critical_loc": 3500, "production_modules": 10,
              "duplicate_authorities": 0, "legacy_production_imports": 0})
    return a


def test_shrinkage_scoreboard():
    r = shrinkage_scoreboard(_before(), _after())
    assert r["verdict"] == "SHRINKAGE_PASS"
    assert r["hard_down"] is True
    assert r["zero"] is True


def test_shrinkage_incomplete_when_no_down():
    r = shrinkage_scoreboard(_before(), _before())
    assert r["verdict"] == "SHRINKAGE_INCOMPLETE"


def test_trust_scoreboard():
    r = trust_scoreboard(_before(), _after(), safety="PASS")
    assert r["verdict"] == "TRUST_PASS"
    bad = _after()
    bad["replay_coverage"] = 0.80
    assert trust_scoreboard(_before(), bad)["verdict"] == "TRUST_REGRESSED"


def test_release_gates_and_certificate():
    authority = dict(AUTHORITY_GATE)
    authority["report_decision_authority"] = 0
    authority["legacy_production_paths"] = 0
    shrink = shrinkage_scoreboard(_before(), _after())
    trust = trust_scoreboard(_before(), _after(), safety="PASS")
    deletion = {"verdict": "DELETE_COMPLETE"}
    gates = release_gates(authority, shrink, trust, deletion)
    assert gates["verdict"] == "ALL_GATES_PASS"
    cert = convergence_certificate(gates, shrink, trust)
    assert cert["verdict"] == "CONVERGED"


def test_certificate_rejected_on_trust_regression():
    authority = dict(AUTHORITY_GATE)
    authority["report_decision_authority"] = 0
    authority["legacy_production_paths"] = 0
    shrink = shrinkage_scoreboard(_before(), _after())
    bad = _after()
    bad["replay_coverage"] = 0.80
    trust = trust_scoreboard(_before(), bad, safety="PASS")
    deletion = {"verdict": "DELETE_COMPLETE"}
    gates = release_gates(authority, shrink, trust, deletion)
    cert = convergence_certificate(gates, shrink, trust)
    assert cert["verdict"] == "REJECTED"


def test_definition_of_done():
    checks = {q: True for q in (
        "one_production_decision_path", "single_canonical_authority",
        "active_features_down", "decision_critical_loc_down",
        "legacy_production_path_zero", "duplicate_authority_zero",
        "unwired_active_feature_zero", "golden_replay_oos_not_regressed",
        "failure_injection_zero_escaped",
        "retired_code_physically_deleted")}
    r = definition_of_done_10(checks)
    assert r["verdict"] == "MTR_SUCCESS"
    checks["retired_code_physically_deleted"] = False
    assert definition_of_done_10(checks)["verdict"] == "MTR_INCOMPLETE"


def test_regression_evidence_defaults():
    r = regression_evidence()
    # MTR Closure：缺证据 → NOT_PROVEN（不是 PASS）
    assert r["replay"] == "NOT_PROVEN"
    assert r["safety_failure_injection"] == "NOT_PROVEN"


def test_feature_manifest_artifact():
    g = {"nodes": {
        "decision.governance": {"production_reachable": True,
                                "authority": "FINAL_TARGET"},
        "orphan_mod": {"production_reachable": False,
                       "authority": "NONE"}}}
    frozen = {
        "governance_finalize": {"owner": "decision.governance",
                                "state": "ACTIVE",
                                "production_required": True},
        "orphan_feature": {"owner": "orphan_mod", "state": "ACTIVE",
                           "production_required": True},
        "retired_feature": {"owner": "decision.governance",
                            "state": "RETIRED",
                            "production_required": False},
    }
    r = production_feature_manifest_artifact(
        g, {"classifications": {}}, release_id="REL-1",
        frozen_manifest=frozen)
    assert r["features"]["governance_finalize"]["state"] == "ACTIVE"
    assert r["features"]["retired_feature"]["state"] == "RETIRED"
    # Frozen Manifest 与 Graph 独立比对：orphan_feature 未接线 → unwired
    assert r["unwired_active"] == ["orphan_feature"]
    assert r["verification"]["verdict"] == "MANIFEST_UNWIRED"


def test_frozen_manifest_wired_on_real_tree():
    """Sprint B：Frozen Manifest 的 ACTIVE 在真实 Authority Graph 上
    全部 wired，且 v10 ACTIVE < v9 baseline、newly_active = 0。"""
    from pathlib import Path
    from QCFP_MTF.governance.pwc2_authority_graph import \
        build_authority_graph
    qcfp_root = Path(CORE_DIR) / "QCFP_MTF"
    graph = build_authority_graph(qcfp_root)
    v = verify_frozen_manifest(graph, FROZEN_PRODUCTION_MANIFEST)
    assert v["verdict"] == "MANIFEST_WIRED"
    assert v["unwired_active"] == []
    assert v["unknown_owner"] == []
    assert v["forbidden_dependency_active"] == []
    d = active_feature_diff(V9_PRODUCTION_BASELINE_MANIFEST,
                            FROZEN_PRODUCTION_MANIFEST)
    assert d["verdict"] == "ACTIVE_DOWN"
    assert d["after_active_count"] < d["before_active_count"]
    assert d["newly_active"] == []
    assert "decision.score_calculator" in d["retired"]


def test_critical_loc_metrics_real_tree():
    """Sprint B：Critical LOC 只统计 Production Roots 可达代码，
    并标记 decision_affecting 模块。"""
    from pathlib import Path
    from QCFP_MTF.governance.pwc2_authority_graph import \
        build_authority_graph
    qcfp_root = Path(CORE_DIR) / "QCFP_MTF"
    m = critical_loc_metrics(build_authority_graph(qcfp_root))
    assert m["reachable_module_count"] > 0
    assert m["reachable_loc"] > 0
    assert m["decision_critical_loc"] > 0
    assert "decision.engine" in m["reachable_modules"]
    assert all(isinstance(x, str) for x in m["decision_critical_modules"])


def test_freeze_mtr_baseline_immutable(tmp_path=None):
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "mtr_baseline.json"
        r1 = freeze_mtr_baseline({"paths": 3}, path, "REL-1")
        assert r1["frozen"] is True
        r2 = freeze_mtr_baseline({"paths": 1}, path, "REL-2")
        assert r2["frozen"] is False
        assert "不可变" in r2["reason"]


def test_evaluate_mtr_not_proven_without_evidence():
    r = evaluate_mtr({})
    assert r["verdict"] == "NOT_PROVEN"
    assert "authority_graph" in r["missing_evidence"]


def test_evaluate_mtr_success_with_bundle():
    bundle = {
        "authority_graph": {"executable_decision_paths": 1,
                            "duplicate_authorities": False,
                            "legacy_production_paths": False},
        "feature_manifest": {"active_features_down": True,
                             "unwired_active": []},
        "loc_metrics": {"decision_critical_loc_down": True},
        "golden_result": {"schema": "GOLDEN-2", "status": "PASS",
                          "n_total": 3, "n_failed": 0,
                          "golden_corpus_version":
                              "GOLDEN-CONSTITUTION-1",
                          "golden_corpus_hash":
                              "4999e192fb300534"},
        "replay_result": {"schema": "REPLAY-2",
                          "n_current_release": 5,
                          "n_eligible": 5, "n_ineligible": 0,
                          "n_exact": 5, "n_mismatch": 0,
                          "n_replay_exception": 0,
                          "eligible_rate": 1.0, "exact_rate": 1.0,
                          "critical_mismatch": 0},
        "oos_result": {"schema": "OOS-2", "status": "OOS_PASS",
                       "comparable": True, "evidence_not_down": True},
        "failure_injection": {"failure_escaped_count": 0},
        "physical_delete": {"all_retired_physically_deleted": True,
                            "retired_removed_count": 2,
                            "residual_references": False},
    }
    r = evaluate_mtr(bundle)
    assert r["verdict"] == "MTR_SUCCESS"
    assert r["certificate"] == "MTR-CONVERGED"


def test_evaluate_mtr_rejects_escaped():
    bundle = {
        "authority_graph": {"executable_decision_paths": 1,
                            "duplicate_authorities": False,
                            "legacy_production_paths": False},
        "feature_manifest": {"active_features_down": True,
                             "unwired_active": []},
        "loc_metrics": {"decision_critical_loc_down": True},
        "golden_result": {"schema": "GOLDEN-2", "status": "PASS",
                          "n_total": 3, "n_failed": 0,
                          "golden_corpus_version":
                              "GOLDEN-CONSTITUTION-1",
                          "golden_corpus_hash":
                              "4999e192fb300534"},
        "replay_result": {"schema": "REPLAY-2",
                          "n_current_release": 5,
                          "n_eligible": 5, "n_ineligible": 0,
                          "n_exact": 5, "n_mismatch": 0,
                          "n_replay_exception": 0,
                          "eligible_rate": 1.0, "exact_rate": 1.0,
                          "critical_mismatch": 0},
        "oos_result": {"schema": "OOS-2", "status": "OOS_PASS",
                       "comparable": True, "evidence_not_down": True},
        "failure_injection": {"failure_escaped_count": 1},
        "physical_delete": {"all_retired_physically_deleted": True,
                            "retired_removed_count": 2,
                            "residual_references": False},
    }
    r = evaluate_mtr(bundle)
    assert "failure_injection_zero_escaped" in r["failures"]


def test_evaluate_mtr_q4_requires_decision_critical_loc():
    """Q4：reachable_loc_down 不能替代 decision_critical_loc_down。"""
    bundle = {
        "authority_graph": {"executable_decision_paths": 1,
                            "duplicate_authorities": False,
                            "legacy_production_paths": False},
        "feature_manifest": {"active_features_down": True,
                             "unwired_active": []},
        "loc_metrics": {"production_reachable_loc_down": True,
                        "decision_critical_loc_down": False},
        "golden_result": {"schema": "GOLDEN-2", "status": "PASS",
                          "n_total": 3, "n_failed": 0,
                          "golden_corpus_version":
                              "GOLDEN-CONSTITUTION-1",
                          "golden_corpus_hash":
                              "4999e192fb300534"},
        "replay_result": {"schema": "REPLAY-2",
                          "n_current_release": 5,
                          "n_eligible": 5, "n_ineligible": 0,
                          "n_exact": 5, "n_mismatch": 0,
                          "n_replay_exception": 0,
                          "eligible_rate": 1.0, "exact_rate": 1.0,
                          "critical_mismatch": 0},
        "oos_result": {"schema": "OOS-2", "status": "OOS_PASS",
                       "comparable": True, "evidence_not_down": True},
        "failure_injection": {"failure_escaped_count": 0},
        "physical_delete": {"all_retired_physically_deleted": True,
                            "retired_removed_count": 2,
                            "residual_references": False},
    }
    r = evaluate_mtr(bundle)
    assert "decision_critical_loc_down" in r["failures"]


def test_evaluate_mtr_q10_requires_all_retired_deleted():
    """Q10：DeclaredRetiredSet ⊆ PhysicallyAbsentSet——
    只删了部分模块不能 PASS。"""
    bundle = {
        "authority_graph": {"executable_decision_paths": 1,
                            "duplicate_authorities": False,
                            "legacy_production_paths": False},
        "feature_manifest": {"active_features_down": True,
                             "unwired_active": []},
        "loc_metrics": {"decision_critical_loc_down": True},
        "golden_result": {"schema": "GOLDEN-2", "status": "PASS",
                          "n_total": 3, "n_failed": 0,
                          "golden_corpus_version":
                              "GOLDEN-CONSTITUTION-1",
                          "golden_corpus_hash":
                              "4999e192fb300534"},
        "replay_result": {"schema": "REPLAY-2",
                          "n_current_release": 5,
                          "n_eligible": 5, "n_ineligible": 0,
                          "n_exact": 5, "n_mismatch": 0,
                          "n_replay_exception": 0,
                          "eligible_rate": 1.0, "exact_rate": 1.0,
                          "critical_mismatch": 0},
        "oos_result": {"schema": "OOS-2", "status": "OOS_PASS",
                       "comparable": True, "evidence_not_down": True},
        "failure_injection": {"failure_escaped_count": 0},
        "physical_delete": {"all_retired_physically_deleted": False,
                            "still_present": ["decision.legacy_x"],
                            "retired_removed_count": 1,
                            "residual_references": []},
    }
    r = evaluate_mtr(bundle)
    assert "retired_code_physically_deleted" in r["failures"]


def test_evaluate_mtr_q8_requires_new_schema():
    """Q8 Final：旧 artifact（无 schema / 无 n_current_release）→
    即使字段值看起来全 PASS 也必须是 NOT_PROVEN。"""
    bundle = {
        "authority_graph": {"executable_decision_paths": 1,
                            "duplicate_authorities": False,
                            "legacy_production_paths": False},
        "feature_manifest": {"active_features_down": True,
                             "unwired_active": []},
        "loc_metrics": {"decision_critical_loc_down": True},
        "golden_result": {"status": "PASS"},
        "replay_result": {"eligible_rate": 1.0, "exact_rate": 1.0,
                          "critical_mismatch": 0,
                          "coverage_not_down": True},
        "oos_result": {"comparable": True, "evidence_not_down": True},
        "failure_injection": {"failure_escaped_count": 0},
        "physical_delete": {"all_retired_physically_deleted": True,
                            "retired_removed_count": 2,
                            "residual_references": False},
    }
    r = evaluate_mtr(bundle)
    assert "golden_replay_oos_not_regressed" in r["failures"]


def test_compare_oos_non_inferiority():
    from QCFP_MTF.scripts.minimal_trusted_release import compare_oos
    tolerances = [
        {"metric": "mdd", "direction": "lower_is_better",
         "max_allowed_regression": 0.05, "hard_or_soft": "hard"},
        {"metric": "wave_capture", "direction": "higher_is_better",
         "max_allowed_regression": 0.05, "hard_or_soft": "hard"},
        {"metric": "turnover", "direction": "lower_is_better",
         "max_allowed_regression": 0.10, "hard_or_soft": "soft"},
    ]
    prev = {"mdd": 0.20, "wave_capture": 0.60, "turnover": 3.0}
    # 改善：MDD 更浅、Wave Capture 更高、Turnover 更低 → 无 regression
    good = {"mdd": 0.15, "wave_capture": 0.62, "turnover": 2.4}
    r = compare_oos(prev, good, tolerances)
    assert r["hard_regressions"] == []
    assert r["soft_warnings"] == []
    assert r["hard_regression_count"] == 0
    # 退化：MDD 更深（超 5pp）→ hard regression
    bad = {"mdd": 0.30, "wave_capture": 0.60, "turnover": 3.0}
    regs = compare_oos(prev, bad, tolerances)
    assert any(x["metric"] == "mdd" and x["hard"]
               for x in regs["hard_regressions"])


def test_compare_oos_soft_regression_is_warning_only():
    """soft regression 只进 soft_warnings，不能阻断 evidence_not_down。"""
    from QCFP_MTF.scripts.minimal_trusted_release import compare_oos
    tolerances = [
        {"metric": "turnover", "direction": "lower_is_better",
         "max_allowed_regression": 0.10, "hard_or_soft": "soft"},
        {"metric": "mdd", "direction": "lower_is_better",
         "max_allowed_regression": 0.05, "hard_or_soft": "hard"},
    ]
    prev = {"turnover": 3.0, "mdd": 0.20}
    cur = {"turnover": 3.5, "mdd": 0.21}   # soft +0.5；hard +0.01（未超）
    r = compare_oos(prev, cur, tolerances)
    assert r["hard_regressions"] == []
    assert len(r["soft_warnings"]) == 1
    assert r["soft_warnings"][0]["metric"] == "turnover"
    assert r["soft_warning_count"] == 1


def test_validate_non_inferiority_contract():
    from QCFP_MTF.scripts.minimal_trusted_release import \
        validate_non_inferiority_contract
    valid = [
        {"metric": "mdd", "direction": "lower_is_better",
         "max_allowed_regression": 0.05, "hard_or_soft": "hard"},
        {"metric": "wave_capture", "direction": "higher_is_better",
         "max_allowed_regression": 0.05, "hard_or_soft": "soft"},
    ]
    assert validate_non_inferiority_contract(valid) == []
    bad = [
        {"metric": "mdd", "direction": "abc",
         "max_allowed_regression": 0.05, "hard_or_soft": "hard"},
        {"metric": "mdd", "direction": "lower_is_better",
         "max_allowed_regression": -1.0, "hard_or_soft": "hard"},
        {"metric": "mdd", "direction": "lower_is_better",
         "max_allowed_regression": 0.05, "hard_or_soft": "maybe"},
        {"metric": "mdd", "direction": "lower_is_better",
         "max_allowed_regression": 0.05, "hard_or_soft": "hard"},
        {"metric": "", "direction": "lower_is_better",
         "max_allowed_regression": 0.05, "hard_or_soft": "hard"},
    ]
    errors = validate_non_inferiority_contract(bad)
    assert any("direction 无效" in e for e in errors)
    assert any("max_allowed_regression<0" in e for e in errors)
    assert any("hard_or_soft 无效" in e for e in errors)
    assert any("metric 重复" in e for e in errors)
    assert any("metric 缺失" in e for e in errors)


def test_validate_oos_contract():
    from QCFP_MTF.scripts.minimal_trusted_release import \
        validate_oos_contract
    complete = {
        "contract_version": "1", "dataset_id": "D1",
        "data_snapshot_hash": "H", "universe_snapshot_hash": "U",
        "pit_specification_hash": "P", "train_start": "a",
        "train_end": "b", "validation_start": "c",
        "validation_end": "d", "oos_start": "e", "oos_end": "f",
        "cost_model_hash": "C", "execution_model_hash": "E",
        "metric_contract_hash": "M", "previous_release_id": "V9",
        "current_release_id": "V10", "holdout_locked": True,
        "used_in_selection": False, "used_for_tuning": False,
        "pit_validation": {"pit_grade": "A",
                           "pit_violation_count": 0,
                           "future_leakage_count": 0,
                           "universe_leakage_count": 0},
        "non_inferiority": [],
    }
    assert validate_oos_contract(complete) == []
    incomplete = dict(complete)
    del incomplete["dataset_id"]
    assert "dataset_id" in validate_oos_contract(incomplete)
    no_pit = dict(complete)
    del no_pit["pit_validation"]
    assert "pit_validation" in validate_oos_contract(no_pit)
    no_ni = dict(complete)
    del no_ni["non_inferiority"]
    assert "non_inferiority" in validate_oos_contract(no_ni)
    no_tuning = dict(complete)
    del no_tuning["used_for_tuning"]
    assert "used_for_tuning" in validate_oos_contract(no_tuning)


def test_load_df_required_table_unavailable_fail_closed():
    """正式 OOS：必需表缺失 → OOSContractError，不是空 DataFrame。"""
    import sqlite3
    from QCFP_MTF.scripts.minimal_trusted_release import (
        OOSContractError, _load_df)
    conn = sqlite3.connect(":memory:")
    try:
        try:
            _load_df(conn, "qcfp_quarterly_structural", required=True)
            raise AssertionError("should raise OOSContractError")
        except OOSContractError as exc:
            assert "REQUIRED_TABLE_UNAVAILABLE" in str(exc)
        # 非必需（探索）路径仍然安全返回空 DataFrame
        df = _load_df(conn, "no_such_table", required=False)
        assert df.empty
    finally:
        conn.close()


def test_load_df_required_table_empty_fail_closed():
    """正式 OOS：必需表存在但为空 → REQUIRED_TABLE_EMPTY。"""
    import sqlite3
    from QCFP_MTF.scripts.minimal_trusted_release import (
        OOSContractError, _load_df)
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE qcfp_quarterly_structural (x TEXT)")
    try:
        try:
            _load_df(conn, "qcfp_quarterly_structural", required=True)
            raise AssertionError("should raise OOSContractError")
        except OOSContractError as exc:
            assert "REQUIRED_TABLE_EMPTY" in str(exc)
    finally:
        conn.close()


def test_oos_contract_hash_canonical():
    """契约冻结哈希必须 canonical：字段顺序不影响 hash。"""
    from QCFP_MTF.scripts.minimal_trusted_release import \
        canonical_contract_hash
    a = {"b": 1, "a": [2, 3]}
    b = {"a": [2, 3], "b": 1}
    assert canonical_contract_hash(a) == canonical_contract_hash(b)
