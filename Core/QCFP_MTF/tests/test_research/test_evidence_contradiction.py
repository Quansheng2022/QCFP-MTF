# coding: utf-8
"""Evidence Contradiction Handling 测试（94 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.research.evidence_contradiction import conclude_evidence, \
    evidence_contradiction_handling


def _conflicting_evidence():
    return {
        "risk": {"verdict": "SUPPORTING", "strength": "STRONG"},
        "return": {"verdict": "CONTRADICTING", "strength": "MILD"},
        "practicality": {"verdict": "SUPPORTING", "strength": "MILD"},
        "turnover": {"verdict": "INCONCLUSIVE", "strength": "MILD"},
    }


def test_conflict_detected_no_average():
    r = evidence_contradiction_handling(_conflicting_evidence())
    assert r["conflict"] is True
    assert r["auto_average_forbidden"] is True
    assert "return" in r["contradicting"]
    assert r["trade_offs"]["return"] == "MILD"


def test_conclude_risk_dominates():
    r = evidence_contradiction_handling(_conflicting_evidence())
    c = conclude_evidence(r, risk_positive=True, return_negative=True,
                          risk_mandate_dominates=True)
    assert c["conclusion"] == "KEEP"
    assert "risk mandate dominates" in c["reason"]


def test_consistent_evidence():
    r = evidence_contradiction_handling({
        "risk": {"verdict": "SUPPORTING"},
        "return": {"verdict": "SUPPORTING"}})
    assert r["conflict"] is False
    assert conclude_evidence(r)["conclusion"] == "KEEP"
