# coding: utf-8
"""Regret Analysis 测试（98 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.evaluation.regret import regret, regret_analysis


def test_regret_basic():
    r = regret(0.115, 0.120, "exit")
    assert r["regret"] == 0.005
    assert r["regret_free"] is False
    assert regret(0.12, 0.12, "exit")["regret_free"] is True


def test_regret_analysis():
    r = regret_analysis(actual_exit=0.115, best_feasible_exit=0.120,
                        actual_entry=0.10, best_feasible_entry=0.095,
                        actual_size=0.3, best_feasible_size=0.4)
    assert len(r["dimensions"]) == 3
    assert r["total_regret"] > 0
    assert r["quality_score"] < 100
