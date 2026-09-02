# coding: utf-8
"""Governance Minimalism Test 测试（98 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.governance_minimalism import \
    governance_minimalism_test


def test_over_complex_governance_simplify():
    r = governance_minimalism_test(
        registries=["r1", "r2", "r3", "r4"],
        certificates=["c1", "c2", "c3"],
        checks=["k1", "k2", "k3", "k4", "k5"])
    assert r["verdict"] == "SIMPLIFY"
    assert len(r["suggestions"]) == 3
    assert r["governance_complexity_score"] == 12


def test_minimal_governance():
    r = governance_minimalism_test(
        registries=["ledger"],
        certificates=["validation"],
        checks=["pit", "replay"])
    assert r["verdict"] == "MINIMAL"
    assert r["suggestions"] == []
