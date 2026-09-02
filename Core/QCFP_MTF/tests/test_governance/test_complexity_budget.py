# coding: utf-8
"""Complexity Budget 测试（32 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.complexity_budget import DEFAULT_BUDGET_LIMITS, \
    budget_consumption


def test_budget_within():
    r = budget_consumption({"features": 50, "core_rules": 30,
                            "free_parameters": 20, "exceptions": 5,
                            "decision_branches": 40})
    assert r["within_budget"] is True
    assert r["over_budget"] == []


def test_budget_over():
    r = budget_consumption({"features": 100, "core_rules": 50})
    assert r["within_budget"] is False
    assert "max_features" in r["over_budget"]
    assert "max_core_rules" in r["over_budget"]


def test_budget_limits():
    assert DEFAULT_BUDGET_LIMITS["max_features"] == 80
    assert DEFAULT_BUDGET_LIMITS["max_exceptions"] == 10
