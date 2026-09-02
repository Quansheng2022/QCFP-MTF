# coding: utf-8
"""Evidence Contradiction 报告保留测试（新 94 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.research.evidence_contradiction import \
    contradiction_promotion_report, strong_conflicts


def _evidence():
    return {
        "return": {"verdict": "CONTRADICTING", "strength": "STRONG"},
        "mdd": {"verdict": "SUPPORTING", "strength": "STRONG"},
        "wave_capture": {"verdict": "CONTRADICTING", "strength": "MILD"},
    }


def test_strong_conflicts_identified():
    handling = {"evidence": _evidence()}
    assert strong_conflicts(handling) == ["return"]


def test_report_requires_review():
    r = contradiction_promotion_report(_evidence())
    assert r["conflicts_preserved"] == ["return"]
    assert r["promotion_verdict"] == "REVIEW_REQUIRED"
    assert r["auto_average_forbidden"] is True


def test_no_conflict_promotion_ok():
    r = contradiction_promotion_report({
        "mdd": {"verdict": "SUPPORTING", "strength": "STRONG"}})
    assert r["promotion_verdict"] == "PROMOTION_OK"
