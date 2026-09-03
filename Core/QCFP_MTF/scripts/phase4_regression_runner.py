#!/usr/bin/env python
# coding: utf-8
"""Phase 4 Independent Regression Runner（FGC-1 Validation Evidence）

Judge（governance/phase4.py）不运行 pytest；
本脚本作为独立 Test System 执行 Phase 4 必跑套件：
    phase4_flow（Flow Governance + FGC-1 Bypass）
    bypass（test_governance_bypass 攻击面）
    phase1 / phase3（前序 Phase Gate 回归）
    decision / governance / golden / full_core（全量回归）

并依据 audit/phase4/contracts/acceptance_case_manifest.json 逐 case 执行
positive / boundary / negative / adversarial 四类 Acceptance Cases，
产出 phase4_acceptance_case_results.json
（schema PHASE4-ACCEPTANCE-CASE-RESULTS-1）。
任何 case 结果都来自 pytest/JUnit（Test System），Runner 不构造 PASS。

计数语义与 Phase 3 Runner 一致：JUnit 解析 collected / failed / errors /
skipped，passed = collected - failed - errors - skipped；
skipped 不计为 PASS；任何真实失败（ASSERTION_FAILURE/CODE_ERROR）
→ suite FAIL；仅环境阻塞 → ENVIRONMENT_BLOCKED。

用法：
    python Core/QCFP_MTF/scripts/phase4_regression_runner.py
    python Core/QCFP_MTF/scripts/phase4_regression_runner.py \
        --python .venv/Scripts/python.exe --out audit/phase4
"""

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from phase3_regression_runner import (  # noqa: E402
    _classify_testcase_failure,
    run_suite,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORE_DIR = PROJECT_ROOT / "Core"
TESTS_DIR = CORE_DIR / "QCFP_MTF" / "tests"

SUITES = {
    "phase4_flow": [
        str(TESTS_DIR / "test_governance" / "test_flow_governance.py"),
        str(TESTS_DIR / "test_governance" / "test_governance_bypass.py"),
    ],
    "bypass": [
        str(TESTS_DIR / "test_governance" / "test_governance_bypass.py"),
    ],
    "phase1": [
        str(TESTS_DIR / "test_governance" / "test_phase1.py"),
    ],
    "phase3": [
        str(TESTS_DIR / "test_governance" / "test_phase3.py"),
    ],
    "decision": [str(TESTS_DIR / "test_decision")],
    "governance": [str(TESTS_DIR / "test_governance")],
    "golden": [str(TESTS_DIR / "test_golden")],
    "full_core": [str(TESTS_DIR)],
}

REQUIRED_SUITES = ("phase4_flow", "bypass", "phase1", "phase3",
                   "decision", "governance", "golden", "full_core")

ACCEPTANCE_CATEGORIES = ("positive", "boundary", "negative", "adversarial")
PIPELINE_TEST_REL = (
    "Core/QCFP_MTF/tests/test_governance/"
    "test_phase4_evidence_integrity.py")


def suite_targets(name: str, ignore_pipeline_test: bool = False) -> list:
    """返回套件 pytest targets；可选 --ignore 自引用 pipeline 测试。"""
    targets = list(SUITES[name])
    if ignore_pipeline_test and name in ("governance", "full_core"):
        targets += ["--ignore",
                    str(TESTS_DIR / "test_governance" /
                        "test_phase4_evidence_integrity.py")]
    return targets


def load_case_manifest(path: Path) -> dict:
    """加载 Acceptance Case Manifest（Contract Authority）。"""
    if not path.exists():
        raise SystemExit(f"acceptance_case_manifest.json 缺失: {path}")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "PHASE4-ACCEPTANCE-CASES-1":
        raise SystemExit("acceptance_case_manifest schema != "
                         "PHASE4-ACCEPTANCE-CASES-1")
    for category in ACCEPTANCE_CATEGORIES:
        cases = manifest.get(category) or []
        if not cases:
            raise SystemExit(
                f"acceptance_case_manifest required category 为空: "
                f"{category}")
        for case in cases:
            if not case.get("case_id") or not case.get("pytest_nodeid"):
                raise SystemExit(
                    f"acceptance_case_manifest {category} 条目缺少 "
                    f"case_id/pytest_nodeid")
    return manifest


def _parse_case_junit(path: Path) -> dict:
    """从 JUnit 解析逐 testcase 结果（含 PASS）。"""
    root = ET.parse(str(path)).getroot()
    suite = root.find("testsuite")
    if suite is None:
        return {"collected": 0, "cases": [], "counts": {
            "passed": 0, "failed": 0, "errors": 0, "skipped": 0}}
    collected = int(suite.get("tests", 0))
    cases = []
    counts = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    for case in suite.iter("testcase"):
        name = case.get("name", "")
        classname = case.get("classname", "")
        message = ""
        kind = "PASS"
        if case.find("skipped") is not None:
            kind = "SKIPPED"
            counts["skipped"] += 1
        else:
            for node_kind in ("failure", "error"):
                node = case.find(node_kind)
                if node is not None:
                    kind = "ERROR" if node_kind == "error" else "FAIL"
                    message = (node.get("message", "") or "")[:500]
                    counts["failed" if node_kind == "failure"
                           else "errors"] += 1
                    break
            if kind == "PASS":
                counts["passed"] += 1
        classification = _classify_testcase_failure(
            name, classname, message) if kind != "PASS" else "PASS"
        cases.append({
            "test": name,
            "classname": classname,
            "kind": kind,
            "message": message,
            "classification": classification,
        })
    return {"collected": collected, "cases": cases, "counts": counts}


def _category_status(counts: dict, cases: list, returncode: int) -> str:
    real = [c for c in cases
            if c.get("kind") in ("FAIL", "ERROR")
            and c.get("classification")
            in ("ASSERTION_FAILURE", "CODE_ERROR")]
    env = [c for c in cases
           if c.get("kind") in ("FAIL", "ERROR")
           and c.get("classification") == "ENVIRONMENT_BLOCKED"]
    if real:
        return "FAIL"
    if env:
        return "ENVIRONMENT_BLOCKED"
    if counts.get("skipped"):
        return "INCOMPLETE"
    return "PASS" if returncode == 0 else "FAIL"


def _run_category(python_exe: str, category: str, manifest_cases: list,
                  junit_path: Path) -> dict:
    """执行 manifest 中某个 category 的全部 pytest nodeid。"""
    expected = len(manifest_cases)
    nodeid_by_test = {}
    manifest_by_test = {}
    targets = []
    for case in manifest_cases:
        nodeid = case["pytest_nodeid"]
        nodeid_by_test[nodeid.rsplit("::", 1)[-1]] = case["case_id"]
        manifest_by_test[nodeid.rsplit("::", 1)[-1]] = case
        rel = nodeid.split("::", 1)[0]
        targets.append(str(PROJECT_ROOT / rel) +
                       "::" + nodeid.rsplit("::", 1)[-1])
    proc = subprocess.run(
        [python_exe, "-m", "pytest", *targets, "-q", "--tb=short",
         "--junitxml", str(junit_path)],
        capture_output=True, text=True)
    parsed = _parse_case_junit(junit_path) if junit_path.exists() else {
        "collected": 0, "cases": [], "counts": {
            "passed": 0, "failed": 0, "errors": 0, "skipped": 0}}
    cases_out = []
    for rec in parsed["cases"]:
        rec = dict(rec)
        rec["case_id"] = nodeid_by_test.get(rec["test"], "")
        rec["pass"] = rec["kind"] == "PASS"
        entry = manifest_by_test.get(rec["test"], {})
        rec["input_hash"] = entry.get("input_hash", "")
        rec["expected_hash"] = entry.get("expected_hash", "")
        rec["actual_hash"] = hashlib.sha256(
            json.dumps({"kind": rec["kind"], "pass": rec["pass"]},
                       sort_keys=True, ensure_ascii=False)
            .encode("utf-8")).hexdigest()
        cases_out.append(rec)
    counts = dict(parsed["counts"])
    counts["collected"] = parsed["collected"]
    status = _category_status(counts, cases_out, proc.returncode)
    executed = parsed["collected"]
    if executed != expected and status == "PASS":
        status = "NOT_PROVEN"
    return {
        "category": category,
        "expected": expected,
        "executed": executed,
        "passed": counts.get("passed", 0),
        "failed": counts.get("failed", 0),
        "errors": counts.get("errors", 0),
        "skipped": counts.get("skipped", 0),
        "status": status,
        "cases": cases_out,
        "mismatch": executed != expected,
        "rule": "Test System 逐 case 执行 manifest；expected == executed；"
                "任何真实失败 → FAIL；skipped → INCOMPLETE；"
                "缺失/不匹配 → NOT_PROVEN",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase 4 Independent Regression Evidence Runner")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--out",
                        default=str(PROJECT_ROOT / "audit" / "phase4"))
    parser.add_argument(
        "--case-manifest",
        default=str(PROJECT_ROOT / "audit" / "phase4" / "contracts" /
                    "acceptance_case_manifest.json"))
    parser.add_argument("--suites", nargs="*",
                        default=list(SUITES.keys()),
                        help="subset: phase4_flow bypass phase1 phase3 "
                             "decision governance golden full_core")
    parser.add_argument(
        "--ignore-pipeline-test", action="store_true",
        help="Test System 重生成证据时忽略自引用 pipeline 测试（该测试在 "
             "证据生成后单独显式运行；避免读写同一份 audit 产物的竞态）")
    args = parser.parse_args(argv)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    results = {}
    with tempfile.TemporaryDirectory() as td:
        junit_dir = Path(td)
        for name in args.suites:
            if name not in SUITES:
                results[name] = {"status": "NOT_RUN",
                                 "reason": f"unknown suite: {name}"}
                continue
            results[name] = run_suite(
                args.python, name,
                suite_targets(name, args.ignore_pipeline_test),
                                      junit_dir)
    statuses = [v.get("status") for v in results.values()]
    missing = [s for s in REQUIRED_SUITES if s not in results]
    if any(s == "FAIL" for s in statuses):
        verdict = "FAIL"
    elif missing:
        verdict = "NOT_PROVEN"
    elif any(s in ("ENVIRONMENT_BLOCKED", "NOT_RUN", "INCOMPLETE")
             for s in statuses):
        verdict = "NOT_PROVEN"
    elif all(s == "PASS" for s in statuses):
        verdict = "PASS"
    else:
        verdict = "NOT_PROVEN"
    summary = {
        "schema": "PHASE4-REGRESSION-1",
        "generated_by": "TEST_SYSTEM",
        "generated_at_utc": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "python": args.python,
        "required_suites": list(REQUIRED_SUITES),
        "missing_suites": missing,
        "suites": results,
        "verdict": verdict,
        "rule": "Judge 只消费本文件；缺失 required suite / "
                "ENVIRONMENT_BLOCKED / INCOMPLETE → NOT_PROVEN；"
                "任何 suite FAIL → PHASE4_FAIL；"
                "skipped 不计为 passed；PASS 要求 skipped=0",
    }
    (out_dir / "phase4_regression_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8")

    # Acceptance Case Evidence（Test System 逐 case 执行）
    manifest = load_case_manifest(Path(args.case_manifest))
    case_results = {}
    with tempfile.TemporaryDirectory() as td2:
        junit_dir2 = Path(td2)
        for category in ACCEPTANCE_CATEGORIES:
            junit = junit_dir2 / f"junit_cases_{category}.xml"
            case_results[category] = _run_category(
                args.python, category, manifest.get(category) or [], junit)
    case_statuses = [v["status"] for v in case_results.values()]
    if any(s == "FAIL" for s in case_statuses):
        case_verdict = "FAIL"
    elif any(s in ("NOT_PROVEN", "NOT_RUN", "ENVIRONMENT_BLOCKED",
                   "INCOMPLETE") for s in case_statuses):
        case_verdict = "NOT_PROVEN"
    elif all(s == "PASS" for s in case_statuses):
        case_verdict = "PASS"
    else:
        case_verdict = "NOT_PROVEN"
    case_evidence = {
        "schema": "PHASE4-ACCEPTANCE-CASE-RESULTS-1",
        "generated_by": "TEST_SYSTEM",
        "generated_at_utc": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "python": args.python,
        "manifest_source": str(Path(args.case_manifest)),
        "categories": case_results,
        "verdict": case_verdict,
        "rule": "四类 Acceptance Cases 由 Test System 逐 case 执行；"
                "Builder/Judge 只消费本文件；缺失或失败 → 不得 PASS",
    }
    (out_dir / "phase4_acceptance_case_results.json").write_text(
        json.dumps(case_evidence, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(json.dumps(
        {"verdict": verdict,
         "suites": {k: v["status"] for k, v in results.items()},
         "acceptance_cases_verdict": case_verdict,
         "acceptance_cases": {
             k: v["status"] for k, v in case_results.items()}},
        ensure_ascii=False, indent=2))
    return 0 if verdict == "PASS" and case_verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
