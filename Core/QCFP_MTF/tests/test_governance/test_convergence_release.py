# coding: utf-8
"""Convergence & Simplification Release 测试（新 10 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.convergence_release import DECLUTTER_ITEMS, \
    FEATURE_LIFECYCLE, convergence_release_report, declutter_audit, \
    feature_lifecycle_check


def _before():
    return {"executable_decision_paths": 5, "duplicate_authorities": 3,
            "legacy_production_imports": 4, "active_feature_count": 60,
            "decision_critical_loc": 5000, "canonical_coverage": 0.80,
            "replay_coverage": 0.85, "invariant_coverage": 0.80,
            "oos_evidence_quality": 0.70}


def _after():
    return {"executable_decision_paths": 1, "duplicate_authorities": 0,
            "legacy_production_imports": 0, "active_feature_count": 40,
            "decision_critical_loc": 3200, "canonical_coverage": 0.95,
            "replay_coverage": 0.98, "invariant_coverage": 0.95,
            "oos_evidence_quality": 0.90}


def test_converged_release():
    r = convergence_release_report(_before(), _after())
    assert r["converged"] is True
    assert r["verdict"] == "CONVERGED"
    assert r["kpis"]["executable_decision_paths"]["direction"] == "DOWN"
    assert r["kpis"]["canonical_coverage"]["direction"] == "UP"
    assert r["regressed"] == []


def test_regression_detected():
    after = _after()
    after["duplicate_authorities"] = 4
    r = convergence_release_report(_before(), after)
    assert r["converged"] is False
    assert r["verdict"] == "REGRESSION_ACTION_REQUIRED"
    assert "duplicate_authorities" in r["regressed"]


def test_feature_lifecycle_manifest():
    r = feature_lifecycle_check({
        "Permission": "ACTIVE",
        "LegacyScore": "RETIRED",
        "NewIdea": "DEFINED",
        "HalfWired": "WEIRD_STATE"})
    assert r["manifest_valid"] is False
    assert r["invalid"] == ["HalfWired"]
    assert r["production_manifest"] == ["Permission"]
    assert FEATURE_LIFECYCLE[4] == "ACTIVE"


def test_declutter_audit():
    r = declutter_audit({item: False for item in DECLUTTER_ITEMS})
    assert r["all_closed"] is True
    r2 = declutter_audit({"legacy_decision_authority": True})
    assert r2["all_closed"] is False
    assert r2["action_required"] == ["legacy_decision_authority"]
    assert r2["results"]["legacy_decision_authority"]["verdict"] == \
        "ACTION_REQUIRED"
