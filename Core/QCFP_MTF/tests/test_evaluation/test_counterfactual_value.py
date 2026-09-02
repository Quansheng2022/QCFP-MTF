# coding: utf-8
"""Counterfactual Decision Value 测试（42 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.evaluation.counterfactual_value import counterfactual_engine, \
    counterfactual_value


def test_counterfactual_value():
    r = counterfactual_value(0.08, 0.05, "BUY_4pct")
    assert r["decision_value"] == 0.03
    assert r["decision_added_value"] is True


def test_counterfactual_engine():
    r = counterfactual_engine(0.08, {
        "BUY_4pct": 0.05, "NO_TRADE": 0.0, "EXIT_earlier": 0.06,
        "Permission_OFF": 0.03, "Wave_OFF": 0.01})
    assert r["actual_is_best"] is True
    assert r["best_alternative"] == "EXIT_earlier"
    assert r["scenarios"]["Permission_OFF"]["decision_value"] == 0.05
