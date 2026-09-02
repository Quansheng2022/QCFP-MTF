# coding: utf-8
"""Decision Latency Budget 测试（68 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.monitoring.decision_latency_budget import \
    decision_latency_budget, latency_budget_check, latency_regression_check


def _latencies():
    return {"data_ready": 300, "evidence_ready": 150,
            "canonical_decision": 80, "ledger_committed": 40,
            "executable_instruction": 30}


def test_total_latency():
    r = decision_latency_budget(_latencies())
    assert r["total_ms"] == 600.0
    assert len(r["stages"]) == 5


def test_budget_check():
    assert latency_budget_check(600, 1000)["within_budget"] is True
    assert latency_budget_check(1200, 1000)["within_budget"] is False


def test_regression_rollback_advice():
    r = latency_regression_check(600, 900)
    assert r["verdict"] == "ROLLBACK_ADVICE"
    assert r["growth"] == 0.5


def test_regression_acceptable():
    r = latency_regression_check(600, 650)
    assert r["verdict"] == "ACCEPTABLE"
