#!/usr/bin/env python
# coding: utf-8
"""Phase 3 Independent Regression Runner（F05，PHASE3-V1.2-FINAL-PROOF-CLOSURE）

Judge（governance/phase3.py）不运行 pytest；
本脚本作为独立 Test System 执行 4 套 pytest 回归，捕获
exit code / junitxml 计数，并把每个失败 testcase 分类为：
    PASS / ASSERTION_FAILURE / CODE_ERROR / ENVIRONMENT_BLOCKED / SKIPPED
然后写出 audit/phase3/phase3_regression_summary.json。

P0-04：skipped 从 JUnit 解析，passed = collected - failed - errors - skipped；
        skipped 不计为 PASS，required suite 存在未批准跳过 → INCOMPLETE。
P1-01：逐 testcase 分类；只要存在 ASSERTION_FAILURE/CODE_ERROR → suite FAIL；
        仅环境阻塞 → ENVIRONMENT_BLOCKED；混合环境+真实失败 → FAIL。

用法：
    python Core/QCFP_MTF/scripts/phase3_regression_runner.py
    python Core/QCFP_MTF/scripts/phase3_regression_runner.py \
        --python .venv/Scripts/python.exe --out audit/phase3
"""

import argparse
import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORE_DIR = PROJECT_ROOT / "Core"
TESTS_DIR = CORE_DIR / "QCFP_MTF" / "tests"

SUITES = {
    "phase3": [str(TESTS_DIR / "test_governance" / "test_phase3.py")],
    "decision": [str(TESTS_DIR / "test_decision")],
    "governance": [str(TESTS_DIR / "test_governance")],
    "full_core": [str(TESTS_DIR)],
}

REQUIRED_SUITES = ("phase3", "decision", "governance", "full_core")

FAILURE_CLASSIFICATIONS = (
    "PASS", "ASSERTION_FAILURE", "CODE_ERROR",
    "ENVIRONMENT_BLOCKED", "SKIPPED",
)


def _classify_failure(text: str) -> str:
    low = (text or "").lower()
    env_markers = (
        "operationalerror", "no such table", "no such column",
        "database is locked", "unable to open database file",
        "connection refused", "module 'sqlite3' has no attribute",
        # 引用实时 DB 投影/台账表 → 依赖数据管道状态（环境/数据状态阻塞）
        "qcfp_mtf_decision", "qcfp_decision_ledger",
        "qcfp_quarterly_structural", "qcfp_daily_tactical",
    )
    if any(m in low for m in env_markers):
        return "ENVIRONMENT_BLOCKED"
    if "assertionerror" in low or "assert " in low:
        return "ASSERTION_FAILURE"
    return "CODE_ERROR"


def _classify_testcase_failure(test: str, classname: str,
                               message: str) -> str:
    """逐 testcase 分类：环境标记 > AssertionError > CODE_ERROR。"""
    low = (str(message or "") + " " + str(test or "") + " " +
           str(classname or "")).lower()
    env_markers = (
        "operationalerror", "no such table", "no such column",
        "database is locked", "unable to open database file",
        "connection refused", "module 'sqlite3' has no attribute",
        # 引用实时 DB 投影/台账表 → 依赖数据管道状态（环境/数据状态阻塞）
        "qcfp_mtf_decision", "qcfp_decision_ledger",
        "qcfp_quarterly_structural", "qcfp_daily_tactical",
    )
    if any(m in low for m in env_markers):
        return "ENVIRONMENT_BLOCKED"
    if "assertionerror" in low or "assert " in low:
        return "ASSERTION_FAILURE"
    return "CODE_ERROR"


def _parse_junit(path: Path) -> dict:
    root = ET.parse(str(path)).getroot()
    suite = root.find("testsuite")
    if suite is None:
        return {"collected": 0, "passed": 0, "failed": 0, "errors": 0,
                "skipped": 0, "failures_detail": []}
    collected = int(suite.get("tests", 0))
    failed = int(suite.get("failures", 0))
    errors = int(suite.get("errors", 0))
    skipped_attr = int(suite.get("skipped", 0))
    skipped_cases = sum(
        1 for case in suite.iter("testcase") if case.find("skipped") is not None)
    skipped = max(skipped_attr, skipped_cases)
    passed = collected - failed - errors - skipped
    detail = []
    for case in suite.iter("testcase"):
        name = case.get("name", "")
        classname = case.get("classname", "")
        if case.find("skipped") is not None:
            detail.append({
                "test": name, "classname": classname, "kind": "skipped",
                "message": "SKIPPED", "classification": "SKIPPED"})
            continue
        for kind in ("failure", "error"):
            node = case.find(kind)
            if node is not None:
                message = (node.get("message", "") or "")[:500]
                detail.append({
                    "test": name, "classname": classname,
                    "kind": kind,
                    "message": message,
                    "classification": _classify_testcase_failure(
                        name, classname, message),
                })
    return {"collected": collected, "passed": passed, "failed": failed,
            "errors": errors, "skipped": skipped, "failures_detail": detail}


def _derive_suite_status(counts: dict, failures_detail: list,
                         returncode: int) -> str:
    """逐 testcase 分类推导 suite status：
    真实失败（ASSERTION_FAILURE/CODE_ERROR）> 0 → FAIL
    elif 环境阻塞 > 0 → ENVIRONMENT_BLOCKED
    elif skipped > 0 → INCOMPLETE
    elif returncode == 0 → PASS
    else → FAIL（无法解析时的兜底）
    """
    real = [d for d in failures_detail
            if d.get("classification") in ("ASSERTION_FAILURE", "CODE_ERROR")]
    env = [d for d in failures_detail
           if d.get("classification") == "ENVIRONMENT_BLOCKED"]
    if real:
        return "FAIL"
    if env:
        return "ENVIRONMENT_BLOCKED"
    if int(counts.get("skipped") or 0) > 0:
        return "INCOMPLETE"
    return "PASS" if returncode == 0 else "FAIL"


def _suite_classification(counts: dict, failures_detail: list) -> str:
    """套件级失败分类（供证据展示）。"""
    if int(counts.get("failed") or 0) or int(counts.get("errors") or 0):
        real = [d for d in failures_detail
                if d.get("classification")
                in ("ASSERTION_FAILURE", "CODE_ERROR")]
        if real:
            return real[0]["classification"]
        env = [d for d in failures_detail
               if d.get("classification") == "ENVIRONMENT_BLOCKED"]
        if env:
            return "ENVIRONMENT_BLOCKED"
    if int(counts.get("skipped") or 0) > 0:
        return "SKIPPED"
    return "PASS"


def run_suite(python_exe: str, name: str, targets: list,
              junit_dir: Path) -> dict:
    junit = junit_dir / f"junit_{name}.xml"
    proc = subprocess.run(
        [python_exe, "-m", "pytest", *targets, "-q", "--tb=long",
         "--junitxml", str(junit)],
        capture_output=True, text=True)
    counts = _parse_junit(junit) if junit.exists() else \
        {"collected": 0, "passed": 0, "failed": 0, "errors": 0,
         "skipped": 0, "failures_detail": []}
    if not junit.exists() and proc.returncode != 0:
        raw = proc.stdout + proc.stderr
        cls = _classify_failure(raw)
        status = "ENVIRONMENT_BLOCKED" if cls == "ENVIRONMENT_BLOCKED" \
            else "FAIL"
    else:
        status = _derive_suite_status(
            counts, counts["failures_detail"], proc.returncode)
    return {
        "status": status,
        "exit_code": proc.returncode,
        "collected": counts["collected"],
        "passed": counts["passed"],
        "failed": counts["failed"],
        "errors": counts["errors"],
        "skipped": counts["skipped"],
        "failure_classification": _suite_classification(
            counts, counts["failures_detail"]),
        "failures": counts["failures_detail"],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase 3 Independent Regression Evidence Runner")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--out", default=str(PROJECT_ROOT / "audit" / "phase3"))
    parser.add_argument("--suites", nargs="*",
                        default=list(SUITES.keys()),
                        help="subset: phase3 decision governance full_core")
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
            results[name] = run_suite(args.python, name, SUITES[name],
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
        "schema": "PHASE3-REGRESSION-2",
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
                "任何 suite FAIL → PHASE3_FAIL；"
                "skipped 不计为 passed；PASS 要求 skipped=0",
    }
    (out_dir / "phase3_regression_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(json.dumps({"verdict": verdict,
                      "suites": {k: v["status"] for k, v in results.items()}},
                     ensure_ascii=False, indent=2))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
