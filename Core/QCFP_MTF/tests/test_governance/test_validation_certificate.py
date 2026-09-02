# coding: utf-8
"""ValidationCertificate 测试（14 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.validation_certificate import \
    CERTIFICATE_GATES, certificate_display, validation_certificate


def _all_pass():
    return {g: True for g in CERTIFICATE_GATES}


def test_certified():
    c = validation_certificate(_all_pass(), certificate_id="CERT-1")
    assert c["overall_status"] == "CERTIFIED"
    assert c["is_validated"] is True
    assert c["display_status"] == "RESEARCH VALIDATED"


def test_missing_gates_unknown():
    c = validation_certificate({})     # 全部缺失 → UNKNOWN
    assert c["overall_status"] == "UNKNOWN"
    assert c["display_status"] == "UNKNOWN"
    assert "RESEARCH VALIDATED" not in c["display_status"]


def test_failed_gates_not_certified():
    checks = _all_pass()
    checks["oos"] = False
    c = validation_certificate(checks)
    assert c["overall_status"] == "NOT_CERTIFIED"
    assert c["display_status"] == "NOT CERTIFIED"


def test_no_certificate_display_unknown():
    assert certificate_display(None) == "UNKNOWN"
