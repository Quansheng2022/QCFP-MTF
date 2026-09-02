# coding: utf-8
"""Complexity Ceiling v2 测试（新 50 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.complexity_ceiling import AUTHORITY_CEILING_TARGETS, \
    active_feature_gate, authority_ceiling_check, release_complexity_report


def test_authority_targets():
    assert AUTHORITY_CEILING_TARGETS["canonical_decision_authority"] == 1
    assert AUTHORITY_CEILING_TARGETS["report_decision_authority"] == 0


def test_authority_within_ceiling():
    authorities = {k: v for k, v in AUTHORITY_CEILING_TARGETS.items()}
    r = authority_ceiling_check(authorities)
    assert r["within_ceiling"] is True


def test_authority_over_ceiling():
    authorities = dict(AUTHORITY_CEILING_TARGETS)
    authorities["permission_authority"] = 2
    r = authority_ceiling_check(authorities)
    assert r["within_ceiling"] is False
    assert r["violations"][0]["authority"] == "permission_authority"


def test_active_feature_gate_requires_six_evidences():
    evidence = {k: True for k in (
        "existing_core_cannot_solve", "oos_incremental_value",
        "ablation_value", "stress_robustness",
        "retail_practicality", "complexity_cost_acceptable")}
    r = active_feature_gate("NewGate", evidence)
    assert r["verdict"] == "ACTIVE_ELIGIBLE"
    r2 = active_feature_gate("NewGate", {"oos_incremental_value": True})
    assert r2["verdict"] == "RESEARCH_ONLY"


def test_release_complexity_report():
    r = release_complexity_report({"complexity_rose": True},
                                  incremental_value_evidence=False)
    assert r["verdict"] == "PROMOTION_REJECTED"
    r2 = release_complexity_report({"complexity_rose": True},
                                   incremental_value_evidence=True)
    assert r2["verdict"] == "PROMOTION_OK"
