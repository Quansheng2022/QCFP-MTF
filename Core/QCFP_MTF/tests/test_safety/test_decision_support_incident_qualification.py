# coding: utf-8
"""Decision Support Incident Qualification 测试（P1-8）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.safety.decision_support_incident_qualification import (
    CASE_RUNNERS, DECISION_INCIDENT_CASES,
    run_decision_support_incident_qualification)


def test_all_ten_decision_cases():
    assert len(DECISION_INCIDENT_CASES) == 10
    assert set(CASE_RUNNERS) == set(DECISION_INCIDENT_CASES)


def test_decision_support_incident_zero_escaped():
    r = run_decision_support_incident_qualification()
    assert r["incident_cases_total"] == 10
    assert r["escaped"] == 0
    assert r["status"] == "DECISION_SUPPORT_INCIDENT_QUALIFIED"
    assert all(v for v in r["gates"].values())


def test_future_leak_blocked():
    r = run_decision_support_incident_qualification()
    case = next(x for x in r["results"]
                if x["case_id"] == "PIT_FUTURE_LEAK")
    assert case["escaped"] is False
    assert "FeatureGateError" in case["actual_behavior"]
