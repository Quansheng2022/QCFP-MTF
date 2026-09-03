# coding: utf-8
"""P1-EVID-01：Evidence Integrity 测试

核心断言：
    * Builder 不得构造 PASS / n_failed=0 —— 事实必须来自 Test System；
    * skipped / missing / tampered / FAIL 一律不得变成 PHASE4_PASS；
    * 真实 Runner → Builder → Judge 管线闭环。

Judge 的 synthetic scaffold 测试保留在 test_phase4.py；
本文件新增真实证据语义测试。
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_CORE_DIR = _PROJECT_ROOT / "Core"
_SCRIPTS = _CORE_DIR / "QCFP_MTF" / "scripts"
if str(_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(_CORE_DIR))
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import phase4_evidence_builder as builder  # noqa: E402


def _suite(status="PASS", collected=10, passed=10, failed=0, errors=0,
           skipped=0) -> dict:
    return {"status": status, "exit_code": 0, "collected": collected,
            "passed": passed, "failed": failed, "errors": errors,
            "skipped": skipped, "failure_classification": "PASS",
            "failures": []}


def _regression(suites=None) -> dict:
    names = ("phase4_flow", "bypass", "phase1", "phase3",
             "decision", "governance", "golden", "full_core")
    suites = suites or {n: _suite() for n in names}
    statuses = [s.get("status") for s in suites.values()]
    return {"schema": "PHASE4-REGRESSION-1", "verdict":
            "PASS" if all(s == "PASS" for s in statuses) else "NOT_PROVEN",
            "suites": suites, "missing_suites": []}


def _case_evidence(status="PASS") -> dict:
    categories = {}
    for cat in ("positive", "boundary", "negative", "adversarial"):
        categories[cat] = {
            "expected": 2, "executed": 2, "passed": 2, "failed": 0,
            "errors": 0, "skipped": 0, "status": status,
            "cases": [{"case_id": f"{cat}-1", "pass": True,
                       "kind": "PASS"}],
        }
    return {"schema": "PHASE4-ACCEPTANCE-CASE-RESULTS-1",
            "verdict": status, "categories": categories}


def test_builder_derives_golden_from_regression():
    """Golden 投影必须保留 Test System 的 counts/status，不得改写。"""
    reg = _regression()
    reg["suites"]["golden"] = _suite(collected=20, passed=19,
                                     failed=0, errors=1)
    assert builder._validate_regression_payload(reg) != []
    ok_reg = _regression()
    assert builder._validate_regression_payload(ok_reg) == []


def test_golden_failure_cannot_be_overridden():
    reg = _regression()
    reg["suites"]["golden"] = _suite(status="FAIL", collected=20,
                                     passed=19, failed=1)
    problems = builder._validate_regression_payload(reg)
    assert any("golden" in p for p in problems)


def test_golden_skipped_is_not_proven():
    reg = _regression()
    reg["suites"]["golden"] = _suite(collected=20, passed=19,
                                     failed=0, skipped=1)
    problems = builder._validate_regression_payload(reg)
    assert problems


def test_missing_acceptance_category_not_proven():
    evidence = _case_evidence()
    del evidence["categories"]["adversarial"]
    assert builder._validate_case_results(evidence)


def test_empty_required_category_not_proven():
    evidence = _case_evidence()
    evidence["categories"]["positive"]["expected"] = 0
    assert builder._validate_case_results(evidence)


def test_case_failure_propagates_to_acceptance():
    evidence = _case_evidence(status="FAIL")
    evidence["categories"]["adversarial"]["status"] = "FAIL"
    assert builder._validate_case_results(evidence)


def test_builder_does_not_emit_pass_constant():
    """静态检查：Builder 源码不得再构造 status=PASS / n_failed=0 字面量。"""
    src = Path(builder.__file__).read_text(encoding="utf-8")
    assert '"status": "PASS"' not in src
    assert '"n_failed": 0' not in src
    assert 'status = "PASS"' not in src


def test_tampered_regression_counts_rejected():
    reg = _regression()
    suite = reg["suites"]["decision"]
    suite["collected"] = 100
    suite["passed"] = 90
    assert builder._validate_regression_payload(reg)


def test_real_runner_builder_judge_pipeline():
    """真实 Runner→Builder→Judge 闭环（不使用 synthetic _suite()）。

    环境前置：audit/phase4 必须先由 phase4_regression_runner 产出真实
    regression summary（含 golden）与 acceptance case results；否则本测试
    视为环境不满足并直接返回（不伪造 PASS）。
    """
    audit = _PROJECT_ROOT / "audit" / "phase4"
    regression_path = audit / "phase4_regression_summary.json"
    case_path = audit / "phase4_acceptance_case_results.json"
    assert regression_path.exists(), (
        "Acceptance integration 前置缺失：phase4_regression_summary.json "
        "不存在 —— 必须先运行 Test System（Runner）")
    assert case_path.exists(), (
        "Acceptance integration 前置缺失："
        "phase4_acceptance_case_results.json 不存在 —— "
        "必须先运行 Test System（Runner）")
    regression = json.loads(
        regression_path.read_text(encoding="utf-8"))
    assert "golden" in (regression.get("suites") or {}), (
        "Acceptance integration 前置缺失：regression summary 无 golden "
        "suite —— 旧版 Runner 产物不允许静默 PASS")
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        out = tmp / "phase4"
        bundle = out / "bundle"
        bundle.mkdir(parents=True)
        shutil.copytree(audit / "contracts", out / "contracts")
        shutil.copytree(audit / "graphs", out / "graphs")
        shutil.copy2(regression_path, out / "phase4_regression_summary.json")
        shutil.copy2(case_path, out / "phase4_acceptance_case_results.json")
        graph_before = out / "graphs" / "authority_graph_before.json"
        graph_after = out / "graphs" / "authority_graph_after.json"
        rc = builder.main([
            "--base-commit", "cdcab0c",
            "--change-id", "CHG-P4-FGC-1",
            "--release-id", "FGC-CLOSURE-1",
            "--baseline-id", "GOV-BASELINE-4",
            "--out", str(out),
            "--contracts", str(out / "contracts"),
            "--graph-before", str(graph_before),
            "--graph-after", str(graph_after),
            "--regression-summary",
            str(out / "phase4_regression_summary.json"),
            "--case-results", str(out / "phase4_acceptance_case_results.json"),
        ])
        assert rc == 0, "Builder 真实证据管线必须成功"
        assert (out / "bundle" / "evidence_manifest.json").exists()
        from QCFP_MTF.governance.phase4 import phase4_acceptance
        acceptance = phase4_acceptance(out, bundle)
        assert acceptance["verdict"] == "PHASE4_PASS"
        assert acceptance["freeze_state"] == "GOVERNANCE_FREEZE_CANDIDATE"
        assert acceptance["close_record"][
            "bypass_to_software_qualified"] == 0
