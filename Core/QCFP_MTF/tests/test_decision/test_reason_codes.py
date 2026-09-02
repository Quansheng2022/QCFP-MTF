# coding: utf-8
"""Reason Code 标准化测试（33 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.reason_codes import (REASON_CODES,
                                            normalize_reason,
                                            reason_code_stats,
                                            reason_code_summary)


def test_normalize_reason():
    assert normalize_reason("HARD_EXIT") == "HARD_EXIT"
    assert normalize_reason("PERMISSION_BLOCK") == "PERMISSION_BLOCK"
    assert normalize_reason("POSITION_CAP") == "PORTFOLIO_LIMIT"
    assert normalize_reason("DATA_QUALITY_C") == "DATA_DEGRADED"
    assert normalize_reason("weird text") == "weird text"


def test_standard_codes_defined():
    for c in ("WAVE_CONFIRM", "ENTRY_LATE", "PERMISSION_BLOCK",
              "LIQUIDITY_LIMIT", "TIME_STOP", "HARD_EXIT", "REGIME_BREAK"):
        assert c in REASON_CODES


def test_reason_stats():
    decisions = [
        {"primary_reason": "ENTRY_LATE", "secondary_reasons": [],
         "constraint_reasons": []},
        {"primary_reason": "WAVE_CONFIRM", "secondary_reasons": [],
         "constraint_reasons": ["ENTRY_LATE"]},
        {"primary_reason": "NONE", "secondary_reasons": [],
         "constraint_reasons": []},
    ]
    s = reason_code_stats(decisions, code="ENTRY_LATE")
    assert s["count"] == 2
    assert s["total"] == 3
    summary = reason_code_summary(decisions)
    assert summary["ENTRY_LATE"] == 2
