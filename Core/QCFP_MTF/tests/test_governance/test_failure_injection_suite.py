# coding: utf-8
"""Governance Failure Injection Suite 测试（新 48 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.failure_injection import FAILURE_INJECTION_CASES, \
    assert_fail_closed, failure_injection_cases, \
    principle_adversarial_tests


def test_eleven_cases_defined():
    c = failure_injection_cases()
    assert len(c["cases"]) == 11
    assert "pit_timestamp_future" in c["cases"]
    assert "execution_from_raw_proposal" in c["cases"]
    assert all(c["expected"][k] == "REJECT" for k in c["cases"])


def test_fail_closed_detection():
    assert assert_fail_closed("x", "REJECT")["verdict"] == "FAIL_CLOSED"
    assert assert_fail_closed("x", "NO_DECISION")["verdict"] == "FAIL_CLOSED"
    r = assert_fail_closed("x", "TRADE")
    assert r["verdict"] == "CONTINUED_TRADING"
    assert r["violation"] is True


def test_five_principles_adversarial():
    r = principle_adversarial_tests()
    assert len(r["principles"]) == 5
    assert "permission_over_signal" in r["principles"]
    assert "ledger_and_replay" in r["principles"]
    assert len(FAILURE_INJECTION_CASES) == 11
