# coding: utf-8
"""Binding Constraint Frequency 退役证据测试（新 65 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.monitoring.binding_constraint_frequency import \
    liquidity_high_binding_diagnosis, retirement_evidence


def test_zero_binding_zero_value_retire():
    r = retirement_evidence("ExecutionCap", 0.0, 0.001)
    assert r["verdict"] == "RETIRE_REVIEW"
    assert r["retire"] is True


def test_mandatory_governance_kept():
    r = retirement_evidence("Permission", 0.0, 0.0,
                             mandatory_governance=True)
    assert r["verdict"] == "REVIEW"


def test_active_binding_kept():
    r = retirement_evidence("LiquidityCap", 0.18, 0.02)
    assert r["verdict"] == "ACTIVE_BINDING"


def test_liquidity_high_binding_proposal_fix():
    r = liquidity_high_binding_diagnosis(0.65)
    assert r["diagnosis"] == "PROPOSAL_CAPACITY_MISMATCH"
    assert "修改上游 Proposal" in r["guidance"]
