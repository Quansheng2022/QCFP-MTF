# coding: utf-8
"""Simplification Engine 测试（39 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.research.simplification import minimum_effective_system, \
    simplification_engine


def test_simplification_recommended():
    r = simplification_engine(full_sharpe=1.42, simplified_sharpe=1.39,
                              full_complexity=100,
                              simplified_complexity=55)
    assert r["complexity_reduction"] == 0.45
    assert r["recommend_simplification"] is True


def test_simplification_not_recommended_when_sharpe_drops():
    r = simplification_engine(full_sharpe=1.42, simplified_sharpe=1.0,
                              full_complexity=100,
                              simplified_complexity=40)
    assert r["recommend_simplification"] is False


def test_minimum_effective_system():
    cands = {
        "A": {"full_sharpe": 1.4, "simplified_sharpe": 1.38,
              "full_complexity": 100, "simplified_complexity": 60},
        "B": {"full_sharpe": 1.4, "simplified_sharpe": 1.36,
              "full_complexity": 100, "simplified_complexity": 45},
    }
    r = minimum_effective_system(cands)
    assert r["recommend"] is True
    assert r["best"]["name"] == "B"     # 复杂度更低
