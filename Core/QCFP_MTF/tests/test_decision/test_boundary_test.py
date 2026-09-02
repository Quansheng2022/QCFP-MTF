# coding: utf-8
"""Decision Boundary Test 测试（95 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.boundary_test import run_boundary_tests


def test_boundary_suite_passes():
    r = run_boundary_tests()
    assert r["all_pass"] is True
    assert r["status"] == "PASS"
    assert len(r["cases"]) == 5


def test_boundary_cases_cover_no_override():
    r = run_boundary_tests()
    names = {c["name"] for c in r["cases"]}
    assert "B1_CAP_CHAIN" in names
    assert "B2_BLOCK_NO_TRADE" in names
    assert "B3_RISK_BLOCK" in names
    assert "B4_HARD_EXIT_ZERO" in names
