# coding: utf-8
"""Opportunity Competition Engine 测试（46 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.ranking.competition import opportunity_competition


def _opp(code, theme, weight):
    return {"stock_code": code, "theme": theme, "weight": weight}


def test_same_theme_shares_budget():
    opps = [_opp("A", "AI", 0.08), _opp("B", "AI", 0.08),
            _opp("C", "AI", 0.08)]
    r = opportunity_competition(opps, theme_budget=0.15,
                                max_single_weight=0.08)
    assert "AI" in r.over_budget
    assert r.allowed_weights["A"] <= 0.05 + 1e-6
    total = sum(r.allowed_weights.values())
    assert total <= 0.15 + 1e-6


def test_different_themes_no_competition():
    opps = [_opp("A", "AI", 0.08), _opp("B", "Bank", 0.08)]
    r = opportunity_competition(opps, theme_budget=0.15)
    assert r.over_budget == ()
    assert r.allowed_weights["A"] == 0.08


def test_max_single_weight():
    opps = [_opp("A", "AI", 0.20)]
    r = opportunity_competition(opps, max_single_weight=0.10)
    assert r.allowed_weights["A"] == 0.10
