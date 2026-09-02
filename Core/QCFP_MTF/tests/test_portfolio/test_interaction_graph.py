# coding: utf-8
"""Portfolio Interaction Graph 测试（87 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.portfolio.interaction_graph import build_interaction_graph


def _pos(code, sector, theme, factor, weight):
    return {"stock_code": code, "sector": sector, "theme": theme,
            "factor": factor, "beta": 1.0, "weight": weight,
            "institutional_state": "ACCUMULATION"}


def test_interaction_graph_discovers_theme_cluster():
    pos = [_pos("A", "Tech", "AI", "AI", 0.04),
           _pos("B", "Tech", "AI", "AI", 0.04),
           _pos("C", "Tech", "AI", "AI", 0.04),
           _pos("D", "Bank", "Bank", "Bank", 0.04)]
    g = build_interaction_graph(pos)
    assert g["nominal_exposure"] == 0.16
    assert g["effective_exposure"] >= 0.12      # A+B+C 同簇
    assert g["concentration_ratio"] >= 0.75
    assert any("THEME" in e["relations"] for e in g["edges"])
    assert any("INDUSTRY" in e["relations"] for e in g["edges"])


def test_diversified_no_cluster():
    pos = [_pos("A", "Bank", "t1", "f1", 0.05),
           _pos("B", "Tech", "t2", "f2", 0.05)]
    g = build_interaction_graph(pos)
    assert g["concentration_ratio"] < 0.6
