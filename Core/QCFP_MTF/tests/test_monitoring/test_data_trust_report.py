# coding: utf-8
"""Daily Data Trust Report 测试（数据健康检查报告优化）"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.monitoring.data_trust_report import (
    daily_data_trust_report_v2, decision_readiness_v2, pit_health_section,
    source_integrity_check, transformation_health, trust_report_to_md)


def test_source_integrity_pass():
    r = source_integrity_check({k: True for k in (
        "schema", "source_version", "duplicate", "timestamp",
        "price_continuity", "corporate_action", "suspension",
        "cross_source")})
    assert r["overall"] == "PASS"
    assert r["blocks_normal"] is False


def test_source_version_unknown_blocks_normal():
    checks = {k: True for k in (
        "schema", "duplicate", "timestamp", "price_continuity",
        "corporate_action", "suspension", "cross_source")}
    checks["source_version"] = None
    r = source_integrity_check(checks)
    assert r["source_version_unknown"] is True
    assert r["blocks_normal"] is True
    assert r["overall"] == "UNKNOWN"


def test_source_integrity_failure():
    checks = {k: True for k in (
        "schema", "source_version", "duplicate", "timestamp",
        "price_continuity", "corporate_action", "suspension",
        "cross_source")}
    checks["timestamp"] = False
    r = source_integrity_check(checks)
    assert r["overall"] == "FAIL"
    assert r["failures"] == ["timestamp"]


def test_pit_health_section():
    r = pit_health_section({"future_timestamp": 2, "available_date_fail": 1,
                            "pit_grade": "C"})
    assert r["pit_ok"] is False
    assert r["pit_grade"] == "C"
    r2 = pit_health_section({"future_timestamp": 0, "available_date_fail": 0,
                             "pit_grade": "A"})
    assert r2["pit_ok"] is True


def test_transformation_health_fail_on_nan():
    r = transformation_health([
        {"stage": "Price Factors", "input": 300, "output": 300,
         "nan": 0.003, "version": "PF-v3"},
        {"stage": "Flow Factors", "input": 300, "output": 298,
         "nan": 0.12, "version": "FF-v2"}])
    assert r["overall"] == "FAIL"
    assert r["failures"] == ["Flow Factors"]
    assert r["stages"][0]["status"] == "PASS"


def test_transformation_no_telemetry_unknown():
    r = transformation_health(None)
    assert r["overall"] == "UNKNOWN"


def test_pit_missing_metadata_unknown():
    r = pit_health_section({"future_timestamp": 0,
                            "available_date_fail": 0,
                            "pit_grade": "B"})
    assert r["universe_snapshot"] == "UNKNOWN"
    assert r["disclosure_mode"] == "UNKNOWN"


def test_overall_not_normal_when_integrity_unknown():
    from QCFP_MTF.monitoring.data_trust_report import trust_overall_status
    si = source_integrity_check({})
    tr = transformation_health(None)
    pit = pit_health_section({"pit_grade": "B"})
    assert trust_overall_status("NORMAL", si, tr, pit) == "CAUTION"


def test_decision_readiness_four_states():
    assert decision_readiness_v2("NORMAL", "A", True)[
        "readiness"] == "YES"
    assert decision_readiness_v2("CAUTION", "B", True)[
        "readiness"] == "DEGRADED"
    assert decision_readiness_v2("BLOCK", "D", False)[
        "readiness"] == "NO"
    assert decision_readiness_v2(None, "UNKNOWN", False)[
        "readiness"] == "UNKNOWN"


def _assessment():
    return pd.DataFrame([
        {"stock_code": "00700", "data_type": "daily_kline", "rows": 1200,
         "first_date": "2022-01-01", "last_date": "2026-08-28",
         "core_missing_rate": 0.001, "anomalies": 0, "grade": "A",
         "reasons": ""},
        {"stock_code": "00700", "data_type": "daily_moneyflow",
         "rows": 1185, "first_date": "2022-01-01",
         "last_date": "2026-08-28", "core_missing_rate": 0.023,
         "anomalies": 3, "grade": "B", "reasons": ""},
    ])


def test_full_report_structure():
    dhs = {"score": 93.6, "status": "CAUTION", "critical_failures": []}
    ev = {"grade": "B", "cap_scale": 0.6, "pit_valid": True,
          "new_risk_allowed": True, "decision_allowed": True}
    pit = pit_health_section({"future_timestamp": 0,
                              "available_date_fail": 0,
                              "pit_grade": "B"})
    si = source_integrity_check({k: True for k in (
        "schema", "source_version", "duplicate", "timestamp",
        "price_continuity", "corporate_action", "suspension",
        "cross_source")})
    tr = transformation_health([])
    r = daily_data_trust_report_v2(
        _assessment(), dhs, ev, pit, si, tr, "20260828", "v2.5")
    assert r["report"] == "QCFP_MTF DAILY DATA TRUST REPORT"
    assert r["overall"]["decision_readiness"] == "DEGRADED"
    assert "source_integrity" in r
    assert "pit" in r and "transformation" in r
    md = trust_report_to_md(r)
    assert "# QCFP_MTF Daily Data Trust" in md
    assert "## Source Integrity" in md
    assert "## PIT" in md
    assert "## Transformation Health" in md
    assert "## Action" in md
