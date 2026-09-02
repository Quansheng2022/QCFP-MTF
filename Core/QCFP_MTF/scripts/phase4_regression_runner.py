#!/usr/bin/env python
# coding: utf-8
"""Phase 4 Independent Regression Runner（FGC-1 Validation Evidence）

Judge（governance/phase4.py）不运行 pytest；
本脚本作为独立 Test System 执行 Phase 4 必跑套件：
    phase4_flow（Flow Governance + FGC-1 Bypass）
    bypass（test_governance_bypass 攻击面）
    phase1 / phase3（前序 Phase Gate 回归）
    decision / governance / full_core（全量回归）

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
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from phase3_regression_runner import run_suite  # noqa: E402


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
    "full_core": [str(TESTS_DIR)],
}

REQUIRED_SUITES = ("phase4_flow", "bypass", "phase1", "phase3",
                   "decision", "governance", "full_core")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase 4 Independent Regression Evidence Runner")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--out",
                        default=str(PROJECT_ROOT / "audit" / "phase4"))
    parser.add_argument("--suites", nargs="*",
                        default=list(SUITES.keys()),
                        help="subset: phase4_flow bypass phase1 phase3 "
                             "decision governance full_core")
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
    print(json.dumps({"verdict": verdict,
                      "suites": {k: v["status"] for k, v in results.items()}},
                     ensure_ascii=False, indent=2))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
