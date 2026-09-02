# coding: utf-8
"""Duplicate Logic → Release Gate 测试（新 73 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.duplicate_logic_detector import \
    BUSINESS_RULE_PATTERNS, duplicate_authority_release_gate


def test_business_duplicate_blocks_release():
    r = duplicate_authority_release_gate({
        "permission_mapping": ["a.py", "b.py"],
        "helper_format": ["c.py", "d.py"]})
    assert r["release_verdict"] == "RELEASE_BLOCKED"
    assert r["allowed"] is False
    assert "permission_mapping" in r["business_duplicates"]


def test_helper_duplicate_allowed():
    r = duplicate_authority_release_gate({
        "helper_format": ["c.py", "d.py"]})
    assert r["release_verdict"] == "RELEASE_ALLOWED"
    assert r["allowed"] is True


def test_business_patterns_defined():
    assert "final_target_calculation" in BUSINESS_RULE_PATTERNS
    assert "research_validated" in BUSINESS_RULE_PATTERNS
