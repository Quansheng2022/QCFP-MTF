# coding: utf-8
"""Data Quality Gate 测试（29 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.data.quality import (DataQualityGateError,
                                   assert_data_quality_gate,
                                   data_health_score, data_quality_gate,
                                   evidence_quality_contract)
from QCFP_MTF.decision.engine import DecisionConfig, evaluate
from QCFP_MTF.config.settings import DEFAULT_SETTINGS


def test_gate_pass():
    checks = {k: False for k in (
        "missingness", "duplicate", "timestamp", "available_date",
        "price_continuity", "corporate_action", "volume_anomaly",
        "suspension", "outlier", "schema", "source_version")}
    g = data_quality_gate(checks)
    assert g["status"] == "PASS"
    assert assert_data_quality_gate(checks) == "PASS"


def test_gate_empty_unknown_fail_closed():
    """PWC-1（第 2 项）：空 checks → UNKNOWN（≠PASS）。"""
    g = data_quality_gate({})
    assert g["status"] == "UNKNOWN"
    assert g["unknown_checks"]


def test_gate_degraded():
    checks = {k: False for k in (
        "missingness", "duplicate", "timestamp", "available_date",
        "price_continuity", "corporate_action", "volume_anomaly",
        "suspension", "outlier", "schema", "source_version")}
    checks["duplicate"] = True
    g = data_quality_gate(checks)
    assert g["status"] == "DEGRADED"


def test_gate_block():
    g = data_quality_gate({"suspension": True})
    assert g["status"] == "BLOCK"
    try:
        assert_data_quality_gate({"price_continuity": True})
        raise AssertionError("should raise")
    except DataQualityGateError:
        pass


def test_engine_hard_quality_gate():
    row = {"stock_code": "T_DQ", "decision_date": "2026-08-21",
           "c_state": "C↑", "f_state": "F↑", "p_state": "P↑",
           "prev_f_state": "F↑", "monthly_behavior_state": "Improving",
           "tactical_signal": "Breakout", "daily_state": "DAILY_BREAKOUT",
           "risk_level": "Medium", "des_score": 1,
           "chip_stability_confidence": "High", "data_quality": "B",
           "q_position_52w": 0.3,
           "data_quality_checks": {"suspension": True}}
    try:
        evaluate(dict(row), "FLAT", 0.0, DEFAULT_SETTINGS)
        raise AssertionError("should raise DataQualityGateError")
    except DataQualityGateError:
        pass
    snap = evaluate(dict(row), "FLAT", 0.0, DEFAULT_SETTINGS,
                    config=DecisionConfig(use_hard_quality_gate=False))
    assert snap.target_position >= 0


def test_data_health_score_11():
    r = data_health_score()
    assert r["score"] >= 95
    assert r["status"] == "NORMAL"


def test_data_health_band():
    assert data_health_score(completeness=0.5, accuracy=1.0,
                             timeliness=0.8)["status"] == "DEGRADED"
    assert data_health_score(completeness=0.5,
                             accuracy=0.4)["status"] == "BLOCK"


def test_data_health_critical_hard_block():
    r = data_health_score(critical_failures=["volume_anomaly"])
    assert r["status"] == "BLOCK"
    assert r["hard_blocked"] is True
    assert "volume_anomaly" in r["critical_failures"]


def test_evidence_quality_contract_22():
    a = evidence_quality_contract(pit_valid=True, coverage=0.95,
                                  staleness_hours=6, missing_rate=0.02,
                                  source_consistent=True)
    assert a["grade"] == "A"
    assert a["cap_scale"] == 1.0
    c = evidence_quality_contract(pit_valid=True, coverage=0.6,
                                  staleness_hours=60, missing_rate=0.25,
                                  source_consistent=True)
    assert c["grade"] == "C"
    assert c["new_risk_allowed"] is False
    u = evidence_quality_contract(pit_valid=None, coverage=0.9,
                                  staleness_hours=6, missing_rate=0.02,
                                  source_consistent=True)
    assert u["grade"] == "UNKNOWN"
