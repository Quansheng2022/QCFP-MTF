# coding: utf-8
"""Retail Practicality Promotion Hard Gate 测试（Release 3：新 27 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.evaluation.retail_scorecard import practicality_hard_gate, \
    retail_operating_envelope


def test_operating_envelope_versioned():
    r = retail_operating_envelope()
    assert r["policy_version"] == "PRACTICALITY-1.0"
    assert r["envelope"]["trades_per_year_max"] == 120


def test_grade_c_blocks_despite_valid():
    r = practicality_hard_gate(True, "C")
    assert r["verdict"] == "PROMOTION_BLOCKED"
    assert r["allowed"] is False


def test_grade_a_allows():
    r = practicality_hard_gate(True, "A")
    assert r["allowed"] is True
