# coding: utf-8
"""Retail Practicality Promotion 测试（新 29 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.evaluation.retail_scorecard import promotion_requirement, \
    retail_practicality_scorecard


def _good_metrics():
    return {"trades_per_year": 60, "median_holding_days": 20,
            "median_concurrent_positions": 4, "turnover": 1.5,
            "exit_days": 2, "adv_participation": 0.05,
            "max_drawdown": -0.15, "decision_changes_per_month": 5,
            "missed_opportunity": 0.25, "explanation_complexity": 0.4,
            "capital_utilization": 0.5, "false_participation": 0.1}


def test_promotion_allowed_when_both_pass():
    r = retail_practicality_scorecard(_good_metrics())
    assert r["grade"] == "A"
    p = promotion_requirement(True, r["grade"])
    assert p["promotion"] == "ALLOW"


def test_promotion_blocked_without_statistical_validity():
    r = retail_practicality_scorecard(_good_metrics())
    p = promotion_requirement(False, r["grade"])
    assert p["promotion"] == "BLOCK"


def test_promotion_blocked_with_bad_practicality():
    m = _good_metrics()
    m["trades_per_year"] = 900
    m["turnover"] = 20.0
    r = retail_practicality_scorecard(m)
    p = promotion_requirement(True, r["grade"])
    assert p["promotion"] == "BLOCK"
