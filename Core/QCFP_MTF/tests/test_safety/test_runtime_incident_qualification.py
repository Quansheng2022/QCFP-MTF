# coding: utf-8
"""Runtime Incident Qualification 测试（C5）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.safety.runtime_incident_qualification import (
    CASE_RUNNERS, INCIDENT_CASES, run_incident_qualification,
    setup_scenario_conn)


def test_all_ten_cases_defined_and_runnable():
    assert len(INCIDENT_CASES) == 10
    assert set(CASE_RUNNERS) == set(INCIDENT_CASES)
    for case_id in INCIDENT_CASES:
        conn = setup_scenario_conn()
        try:
            r = CASE_RUNNERS[case_id](conn)
        finally:
            conn.close()
        assert r["case_id"] == case_id
        assert "escaped" in r
        assert "expected_behavior" in r
        assert "actual_behavior" in r


def test_incident_qualification_zero_escaped():
    r = run_incident_qualification()
    assert r["incident_cases_total"] == 10
    assert r["escaped"] == 0
    assert r["escaped_cases"] == []
    assert r["status"] == "SMALL_LIVE_ELIGIBLE"
    assert all(v for v in r["gates"].values())


def test_persistence_failure_is_no_new_risk():
    r = run_incident_qualification()
    case = next(x for x in r["results"]
                if x["case_id"] == "CASE_07_EVENT_PERSISTENCE_FAILURE")
    assert case["risk_state"] == "NO_NEW_RISK"
    assert "BROKER_RESPONSE_UNPERSISTED" in case["actual_behavior"]


def test_restart_without_certificate_blocked():
    r = run_incident_qualification()
    case = next(x for x in r["results"]
                if x["case_id"] == "CASE_09_PROCESS_RESTART")
    assert case["escaped"] is False
    assert case["reactivation_status"] == "NOT_REACTIVATED"
