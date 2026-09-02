# coding: utf-8
"""Phase 3 Regression Runner 专项测试（PHASE3-V1.2-FINAL-PROOF-CLOSURE）

P0-04：JUnit skipped 正确解析，skipped 不计为 PASS。
P1-01：逐 testcase 分类：真实断言/代码失败 > 环境阻塞；纯环境 → NOT_PROVEN。
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.scripts.phase3_regression_runner import (
    _classify_testcase_failure, _derive_suite_status, _parse_junit,
    _suite_classification,
)


def _junit(tmp_path: Path, testsuite_xml: str) -> Path:
    path = tmp_path / "junit.xml"
    path.write_text(
        "<?xml version='1.0' encoding='utf-8'?>"
        f"<testsuites>{testsuite_xml}</testsuites>",
        encoding="utf-8")
    return path


def test_skipped_test_not_counted_as_pass(tmp_path):   # A36 (runner)
    path = _junit(tmp_path,
        "<testsuite tests='1' failures='0' errors='0'>"
        "<testcase classname='c' name='test_required'>"
        "<skipped message='missing env'/></testcase></testsuite>")
    counts = _parse_junit(path)
    assert counts["collected"] == 1
    assert counts["passed"] == 0
    assert counts["skipped"] == 1
    assert counts["failed"] == 0
    assert counts["errors"] == 0
    assert counts["failures_detail"][0]["classification"] == "SKIPPED"
    assert _derive_suite_status(counts, counts["failures_detail"], 0) \
        == "INCOMPLETE"
    assert _suite_classification(counts, counts["failures_detail"]) \
        == "SKIPPED"


def test_skipped_attr_parsed_from_testsuite(tmp_path):   # A36 (runner)
    path = _junit(tmp_path,
        "<testsuite skipped='3' tests='3' failures='0' errors='0'>"
        "<testcase classname='c' name='t1'/><testcase classname='c' "
        "name='t2'><skipped/></testcase><testcase classname='c' "
        "name='t3'><skipped/></testcase></testsuite>")
    counts = _parse_junit(path)
    assert counts["skipped"] == 3
    assert counts["passed"] == 0


def test_mixed_environment_and_assertion_is_fail():   # A37 (runner)
    detail = [
        {"classification": "ENVIRONMENT_BLOCKED"},
        {"classification": "ASSERTION_FAILURE"},
    ]
    counts = {"collected": 2, "passed": 0, "failed": 2, "errors": 0,
              "skipped": 0}
    status = _derive_suite_status(counts, detail, 1)
    assert status == "FAIL"
    assert _suite_classification(counts, detail) == "ASSERTION_FAILURE"


def test_pure_environment_failure_is_env_blocked():   # A38 (runner)
    detail = [
        {"classification": "ENVIRONMENT_BLOCKED"},
        {"classification": "ENVIRONMENT_BLOCKED"},
    ]
    counts = {"collected": 2, "passed": 0, "failed": 2, "errors": 0,
              "skipped": 0}
    status = _derive_suite_status(counts, detail, 1)
    assert status == "ENVIRONMENT_BLOCKED"


def test_testcase_classification_env_markers():
    assert _classify_testcase_failure(
        "x", "c", "sqlite3.OperationalError: no such table") \
        == "ENVIRONMENT_BLOCKED"
    assert _classify_testcase_failure(
        "test_db_row", "test_tactical_chain",
        "AssertionError: assert None == 'REDUCE'") == "ASSERTION_FAILURE"
    assert _classify_testcase_failure(
        "x", "c", "TypeError: unsupported operand") == "CODE_ERROR"


def test_pass_suite_with_skip_is_incomplete():
    counts = {"collected": 10, "passed": 9, "failed": 0, "errors": 0,
              "skipped": 1}
    assert _derive_suite_status(counts, [], 0) == "INCOMPLETE"
