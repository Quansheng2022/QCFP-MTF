# coding: utf-8
"""AsOfTimeContract 时间完整性测试（新 21 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.data.asof_contract import TIME_ROLES, asof_time_contract, \
    evidence_time_completeness


def test_evidence_time_completeness_ok():
    r = evidence_time_completeness({
        "as_of_time": "2026-08-20",
        "available_time": "2026-08-21",
        "decision_time": "2026-08-21"})
    assert r["complete"] is True
    assert r["available_before_decision"] is True
    assert r["valid"] is True


def test_evidence_time_missing_fields():
    r = evidence_time_completeness({"decision_time": "2026-08-21"})
    assert r["complete"] is False
    assert "as_of_time" in r["missing"]
    assert "available_time" in r["missing"]
    assert r["valid"] is False


def test_evidence_available_after_decision_invalid():
    r = evidence_time_completeness({
        "as_of_time": "2026-08-20",
        "available_time": "2026-08-22",
        "decision_time": "2026-08-21"})
    assert r["available_before_decision"] is False
    assert r["valid"] is False


def test_asof_contract_causal_order():
    r = asof_time_contract(
        {"available_time": "2026-08-20",
         "execution_time": "2026-08-21",
         "outcome_time": "2026-08-28"},
        decision_time="2026-08-21")
    assert r["pit_valid"] is True
    assert len(r["time_roles"]) == len(TIME_ROLES)
