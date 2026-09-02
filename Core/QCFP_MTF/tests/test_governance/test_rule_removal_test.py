# coding: utf-8
"""Rule Removal Test 测试（83 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.rule_removal_test import rule_removal_test


def _current():
    return {"cagr": 0.12, "sharpe": 0.80, "mdd": -0.12,
            "tail_loss": -0.20, "wave_capture": 0.65, "turnover": 1.8,
            "decision_burden": 6, "retail_practicality": 0.6,
            "binding_constraint_coverage": 0.85}


def test_remove_when_similar_and_simpler():
    cur = _current()
    without = dict(cur)
    without.update({"decision_burden": 3, "retail_practicality": 0.75,
                    "turnover": 1.5})
    r = rule_removal_test(cur, without)
    assert r["verdict"] == "REMOVE"
    assert r["worse_metrics"] == []


def test_keep_when_clearly_worse():
    cur = _current()
    without = dict(cur)
    without.update({"sharpe": 0.30, "mdd": -0.30, "wave_capture": 0.20})
    r = rule_removal_test(cur, without)
    assert r["verdict"] == "KEEP"
    assert "sharpe" in r["worse_metrics"]


def test_review_when_single_worse():
    cur = _current()
    without = dict(cur)
    without.update({"wave_capture": 0.58})
    r = rule_removal_test(cur, without)
    assert r["verdict"] == "REVIEW"
    assert r["worse_metrics"] == ["wave_capture"]
