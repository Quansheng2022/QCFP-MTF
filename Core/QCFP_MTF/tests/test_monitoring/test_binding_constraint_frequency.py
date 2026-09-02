# coding: utf-8
"""Binding Constraint Frequency 测试（65 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.monitoring.binding_constraint_frequency import \
    binding_constraint_frequency, constraint_necessity


def _decisions():
    return [{"binding_constraint": "permission_cap"}] * 18 + \
        [{"binding_constraint": "liquidity_cap"}] * 7 + \
        [{"binding_constraint": "portfolio_cap"}] * 2 + \
        [{"binding_constraint": None}] * 73


def test_frequency():
    r = binding_constraint_frequency(_decisions())
    assert r["total_decisions"] == 100
    assert r["frequency"]["permission_cap"] == 0.18
    assert r["frequency"]["liquidity_cap"] == 0.07
    assert r["top_binding"] == "permission_cap"


def test_active_binding_necessity():
    v = constraint_necessity("Permission", 0.18, 0.02)
    assert v["verdict"] == "ACTIVE_BINDING"


def test_retire_candidate():
    v = constraint_necessity("DrawdownCap", 0.0, 0.001)
    assert v["verdict"] == "RETIRE_CANDIDATE"


def test_review_when_ablation_value():
    v = constraint_necessity("ExecutionCap", 0.0, 0.03)
    assert v["verdict"] == "REVIEW"
