# coding: utf-8
"""Governance Certification 测试（50 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.certification import CERTIFICATION_DIMENSIONS, \
    certification_to_md, governance_certification


def _all_checks():
    checks = {}
    for dim in CERTIFICATION_DIMENSIONS.values():
        for c in dim["checks"]:
            checks[c] = True
    return checks


def test_certified():
    cert = governance_certification(_all_checks())
    assert cert["certified"] is True
    assert cert["status"] == "CERTIFIED"


def test_not_certified():
    checks = _all_checks()
    checks["ledger"] = False
    checks["replay"] = False
    cert = governance_certification(checks)
    assert cert["certified"] is False
    assert cert["status"] == "NOT_CERTIFIED"
    assert "ledger" in cert["dimensions"]["auditable"]["missing"]
    assert "replay" in cert["dimensions"]["backtestable"]["missing"]


def test_certification_to_md():
    md = certification_to_md(governance_certification(_all_checks()))
    assert "Governance Certification" in md
    assert "CERTIFIED" in md
