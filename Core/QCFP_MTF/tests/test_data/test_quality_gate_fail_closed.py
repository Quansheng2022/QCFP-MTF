# coding: utf-8
"""DataQualityGate 绝对 Fail-Closed 测试（PWC-1 第 2 项）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.data.quality import CRITICAL_QUALITY_CHECKS, \
    data_quality_gate


def _clean():
    return {k: False for k in (
        "missingness", "duplicate", "timestamp", "available_date",
        "price_continuity", "corporate_action", "volume_anomaly",
        "suspension", "outlier", "schema", "source_version")}


def test_empty_unknown():
    assert data_quality_gate({})["status"] == "UNKNOWN"


def test_critical_missing_unknown():
    checks = _clean()
    del checks["source_version"]
    assert data_quality_gate(checks)["status"] == "UNKNOWN"


def test_critical_none_unknown():
    checks = _clean()
    checks["schema"] = None
    assert data_quality_gate(checks)["status"] == "UNKNOWN"


def test_all_explicit_pass():
    assert data_quality_gate(_clean())["status"] == "PASS"


def test_critical_anomaly_block():
    checks = _clean()
    checks["available_date"] = True
    assert data_quality_gate(checks)["status"] == "BLOCK"


def test_noncritical_anomaly_degraded():
    checks = _clean()
    checks["duplicate"] = True
    assert data_quality_gate(checks)["status"] == "DEGRADED"


def test_critical_checks_defined():
    assert CRITICAL_QUALITY_CHECKS == {
        "available_date", "price_continuity", "suspension",
        "schema", "source_version"}
