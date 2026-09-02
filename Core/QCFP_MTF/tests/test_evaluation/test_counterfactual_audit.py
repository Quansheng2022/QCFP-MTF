# coding: utf-8
"""Counterfactual Decision Audit 测试（54 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.evaluation.counterfactual_audit import counterfactual_audit, \
    constraint_verdict


def test_audit_binding_and_research_only():
    a = counterfactual_audit(
        "d100", 0.20,
        {"liquidity_cap": 0.45, "permission_cap": 0.60,
         "wave_gate": 0.0})
    assert a["binding_constraint"] == "liquidity_cap"
    assert a["research_only"] is True
    assert a["cannot_rewrite_snapshot"] is True
    assert a["counterfactuals"]["permission_cap"]["delta_vs_actual"] == 0.40


def test_audit_id_deterministic():
    a1 = counterfactual_audit("d1", 0.2, {"liquidity_cap": 0.2})
    a2 = counterfactual_audit("d1", 0.2, {"liquidity_cap": 0.2})
    assert a1["audit_id"] == a2["audit_id"]


def test_constraint_saved_us_from_loss():
    a = counterfactual_audit(
        "d2", 0.20, {"permission_cap": 0.60}, outcome=-0.05)
    v = constraint_verdict(a, realized_return=-0.05)
    assert v["verdict"] == "SAVED_BY_CONSTRAINT"


def test_constraint_missed_opportunity():
    a = counterfactual_audit(
        "d3", 0.20, {"liquidity_cap": 0.45}, outcome=0.30)
    v = constraint_verdict(a, realized_return=0.30)
    assert v["verdict"] == "MISSED_OPPORTUNITY"


def test_verdict_needs_outcome():
    a = counterfactual_audit("d4", 0.20, {"liquidity_cap": 0.45})
    assert constraint_verdict(a)["verdict"] == "NEEDS_OUTCOME"
