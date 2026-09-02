# coding: utf-8
"""Retail Practicality Scorecard 测试（29 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.evaluation.retail_scorecard import retail_practicality_scorecard


def _good_metrics():
    return {"trades_per_year": 50, "median_holding_days": 15,
            "median_concurrent_positions": 4, "turnover": 2.0,
            "exit_days": 2, "adv_participation": 0.05,
            "max_drawdown": -0.15, "decision_changes_per_month": 6,
            "missed_opportunity": 0.3, "explanation_complexity": 0.4,
            "capital_utilization": 0.5, "false_participation": 0.1}


def test_good_scorecard():
    r = retail_practicality_scorecard(_good_metrics())
    assert r["grade"] == "A"
    assert r["failed_metrics"] == []


def test_high_turnover_fails():
    m = _good_metrics()
    m["trades_per_year"] = 900
    m["turnover"] = 20.0
    r = retail_practicality_scorecard(m)
    assert r["grade"] in ("C", "D")
    assert "trades_per_year" in r["failed_metrics"]


def test_missing_metrics_fail_closed():
    r = retail_practicality_scorecard({})
    assert r["grade"] == "D"
