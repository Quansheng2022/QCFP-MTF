# coding: utf-8
"""Reactivation Certificate 引用测试（新 97 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.safety.reactivation_gate import reactivation_requires_certificate


def test_transition_blocked_without_certificate():
    r = reactivation_requires_certificate(
        {"from": "SUSPENDED", "to": "PRODUCTION"}, None)
    assert r["verdict"] == "TRANSITION_BLOCKED"
    assert r["allowed"] is False


def test_transition_allowed_with_certificate():
    r = reactivation_requires_certificate(
        {"from": "SUSPENDED", "to": "PRODUCTION"},
        {"reactivation_certificate_id": "RC-001"})
    assert r["verdict"] == "TRANSITION_ALLOWED"
    assert r["certificate_id"] == "RC-001"


def test_other_transition_not_affected():
    r = reactivation_requires_certificate(
        {"from": "FLAT", "to": "TESTING"}, None)
    assert r["verdict"] == "NOT_SUSPEND_TRANSITION"
