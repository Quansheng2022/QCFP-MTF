# coding: utf-8
"""MTR Closure（Sprint E）：纯裁判 runner 测试。

默认模式只读 artifacts → evaluate_mtr()；缺 artifact → NOT_PROVEN。
--generate-artifacts 是唯一允许运行测量的入口。
"""

import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.scripts.minimal_trusted_release import (
    MTR_ARTIFACT_NAMES, generate_artifacts, judge)


def test_judge_not_proven_without_artifacts():
    with tempfile.TemporaryDirectory() as d:
        r = judge(Path(d), None)
        assert r["verdict"] == "NOT_PROVEN"
        assert r["certificate"] == "MTR-NOT-PROVEN"
        assert set(r["missing_artifacts"]) == set(MTR_ARTIFACT_NAMES)


def test_judge_evaluates_artifacts():
    """给定完整 artifact 集，裁判只读并输出 evaluate_mtr 结果。"""
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
                            "retired_removed_count": 1,
                            "residual_references": []},
    }
    with tempfile.TemporaryDirectory() as d:
        out = Path(d)
        for name in MTR_ARTIFACT_NAMES:
            key = {
                "authority_graph.json": "authority_graph",
                "production_feature_manifest.json": "feature_manifest",
                "critical_loc_diff.json": "loc_metrics",
                "golden_result.json": "golden_result",
                "replay_result.json": "replay_result",
                "oos_result.json": "oos_result",
                "failure_injection_results.json": "failure_injection",
                "physical_delete_result.json": "physical_delete",
                "legacy_production_scan.json": "legacy_scan",
            }[name]
            (out / name).write_text(
                json.dumps(bundle.get(key, {}), ensure_ascii=False),
                encoding="utf-8")
        r = judge(out, None)
        assert r["verdict"] == "MTR_SUCCESS"
        assert r["certificate"] == "MTR-CONVERGED"


def _pass_bundle(**overrides):
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
                            "retired_removed_count": 1,
                            "residual_references": []},
    }
    for k, v in (overrides or {}).items():
        bundle[k] = v
    return bundle


def _evaluate_bundle(bundle):
    from QCFP_MTF.governance.minimal_trusted_release import evaluate_mtr
    return evaluate_mtr(bundle)


def test_q8_fails_when_replay_ineligible():
    r = _evaluate_bundle(_pass_bundle(
        replay_result={"schema": "REPLAY-2", "n_current_release": 5,
                       "n_eligible": 4, "n_ineligible": 1,
                       "n_exact": 4, "n_mismatch": 0,
                       "n_replay_exception": 0,
                       "eligible_rate": 0.8, "exact_rate": 1.0,
                       "critical_mismatch": 0}))
    assert "golden_replay_oos_not_regressed" in r["failures"]


def test_q8_fails_when_replay_mismatch():
    r = _evaluate_bundle(_pass_bundle(
        replay_result={"schema": "REPLAY-2", "n_current_release": 5,
                       "n_eligible": 5, "n_ineligible": 0,
                       "n_exact": 4, "n_mismatch": 1,
                       "n_replay_exception": 0,
                       "eligible_rate": 1.0, "exact_rate": 0.8,
                       "critical_mismatch": 0}))
    assert "golden_replay_oos_not_regressed" in r["failures"]


def test_q8_fails_when_replay_exception():
    r = _evaluate_bundle(_pass_bundle(
        replay_result={"schema": "REPLAY-2", "n_current_release": 5,
                       "n_eligible": 5, "n_ineligible": 0,
                       "n_exact": 5, "n_mismatch": 0,
                       "n_replay_exception": 1,
                       "eligible_rate": 1.0, "exact_rate": 1.0,
                       "critical_mismatch": 0}))
    assert "golden_replay_oos_not_regressed" in r["failures"]


def test_q8_fails_when_golden_corpus_changed():
    r = _evaluate_bundle(_pass_bundle(
        golden_result={"schema": "GOLDEN-2", "status": "PASS",
                       "n_total": 3, "n_failed": 0,
                       "golden_corpus_version": "GOLDEN-OTHER",
                       "golden_corpus_hash":
                           "4999e192fb300534"}))
    assert "golden_replay_oos_not_regressed" in r["failures"]


def test_generate_artifacts_writes_all():
    """Build/CI 测量入口必须生成全部 9 类 artifact（真实代码/DB）。

    MTR Q4 Closure：generator 只读 frozen baseline，绝不现场伪造。
    测试用 fixture baseline 模拟已冻结产物；baseline 缺失时必须报错
    （而不是用 Current source 造一个 V9）。"""
    import logging
    from QCFP_MTF.scripts.minimal_trusted_release import (
        MTR_RELEASE_ID, generate_artifacts)
    qcfp_root = Path(CORE_DIR) / "QCFP_MTF"
    logger = logging.getLogger("test_mtr_generator")
    with tempfile.TemporaryDirectory() as d:
        out = Path(d)
        (out / "critical_loc_baseline.json").write_text(
            json.dumps({
                "release_id": "MERGED_CODE_9",
                "code_hash": "frozen-fixture",
                "baseline": {
                    "reachable_modules": [],
                    "reachable_module_count": 0,
                    "reachable_loc": 0,
                    "decision_critical_modules": [],
                    "decision_critical_loc": 0,
                },
                "immutable": True,
            }, ensure_ascii=False),
            encoding="utf-8")
        generate_artifacts(out, qcfp_root, logger)
        assert all((out / name).exists()
                   for name in MTR_ARTIFACT_NAMES)
        assert MTR_RELEASE_ID


def test_generate_artifacts_fails_closed_without_baseline():
    """critical_loc_baseline 缺失 → 禁止现场伪造 V9 baseline。"""
    import logging
    from QCFP_MTF.scripts.minimal_trusted_release import generate_artifacts
    qcfp_root = Path(CORE_DIR) / "QCFP_MTF"
    logger = logging.getLogger("test_mtr_no_baseline")
    with tempfile.TemporaryDirectory() as d:
        out = Path(d)
        try:
            generate_artifacts(out, qcfp_root, logger)
            raise AssertionError("should raise without baseline")
        except RuntimeError as exc:
            assert "critical_loc_baseline.json 缺失" in str(exc)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_mtr_pure_referee 全部通过 ✅")
