# coding: utf-8
"""Failure Injection Qualification 总验收测试（Release 2：新 20 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.failure_injection import \
    FAILURE_INJECTION_QUALIFICATION_CASES, failure_injection_qualification, \
    qualification_classify, run_failure_qualification


def test_twelve_cases_defined():
    assert len(FAILURE_INJECTION_QUALIFICATION_CASES) == 12
    assert "broker_unknown_ack" in FAILURE_INJECTION_QUALIFICATION_CASES
    assert "broker_position_mismatch" in \
        FAILURE_INJECTION_QUALIFICATION_CASES


def test_classify():
    assert qualification_classify("REJECT") == "BLOCKED_AS_DESIGNED"
    assert qualification_classify("NO_DECISION") == "SAFE_MODE"
    assert qualification_classify("TRADE") == "FAILURE_ESCAPED"


def test_qualification_rejects_on_escape():
    results = {case: "REJECT" for case in
               FAILURE_INJECTION_QUALIFICATION_CASES}
    results["broker_unknown_ack"] = "TRADE"
    r = failure_injection_qualification(results)
    assert r["verdict"] == "RELEASE_REJECTED"
    assert r["failure_escaped"] == ["broker_unknown_ack"]
    assert r["allowed"] is False


def test_qualification_passes_when_all_blocked():
    results = {case: "BLOCKED_AS_DESIGNED" for case in
               FAILURE_INJECTION_QUALIFICATION_CASES}
    r = failure_injection_qualification(results)
    assert r["verdict"] == "RELEASE_QUALIFIED"
    assert r["allowed"] is True


def test_real_injection_12_cases_zero_escaped():
    """MTR Closure（Sprint C）：真实注入 12 类故障，每个 case 都执行
    真实 Production Candidate Path，不得传 fabricated result。"""
    r = run_failure_qualification()
    assert r["cases_executed"] == 12
    assert r["expected_cases"] == 12
    assert r["missing_cases"] == []
    assert r["failure_escaped_count"] == 0
    assert r["verdict"] == "RELEASE_QUALIFIED"
    assert {c["case_id"] for c in r["cases"]} == \
        set(FAILURE_INJECTION_QUALIFICATION_CASES)
    for c in r["cases"]:
        assert c["injected_change"], \
            f"{c['case_id']} 缺少 injected_change（非真实注入）"
        assert c["expected_behavior"] in ("BLOCK", "REJECT", "REFUSED",
                                          "NO_NEW_RISK", "REPLAY_MISMATCH",
                                          "GLOBAL_CHAIN_MISMATCH",
                                          "MISMATCH/NO_NEW_RISK",
                                          "BLOCK_NEW_ORDER")


def test_real_injection_missing_case_not_proven():
    r = run_failure_qualification(cases=["future_pit_timestamp",
                                         "not_a_real_case"])
    assert r["verdict"] == "NOT_PROVEN"
    assert r["failure_escaped_count"] == 0
    assert "not_a_real_case" in r["not_executed"]
    assert r["missing_cases"]  # 11 个未执行的 canonical case
    assert any(c["case_id"] == "not_a_real_case"
               and c["actual_behavior"] == "NOT_EXECUTED"
               for c in r["cases"])
