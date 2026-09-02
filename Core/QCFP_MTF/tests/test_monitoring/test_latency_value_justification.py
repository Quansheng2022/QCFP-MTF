# coding: utf-8
"""Decision Latency 增量价值证明测试（新 68 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.monitoring.decision_latency_budget import \
    latency_regression_check, latency_value_justification


def test_rollback_without_value():
    lat = latency_regression_check(600, 900)
    r = latency_value_justification(lat, complexity_delta=0.3,
                                    oos_incremental_value=0.01)
    assert r["decision"] == "ROLLBACK_COMPLEXITY"
    assert r["rollback"] is True


def test_keep_with_evidence():
    lat = latency_regression_check(600, 900)
    r = latency_value_justification(lat, complexity_delta=0.3,
                                    oos_incremental_value=0.05)
    assert r["decision"] == "KEEP_WITH_EVIDENCE"
    assert r["rollback"] is False


def test_acceptable_latency():
    lat = latency_regression_check(600, 620)
    r = latency_value_justification(lat)
    assert r["decision"] == "ACCEPTABLE"
