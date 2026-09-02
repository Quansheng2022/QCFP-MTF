# coding: utf-8
"""Portfolio Risk Aggregator 测试（16 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.portfolio.aggregator import portfolio_risk_aggregator


def _pos(code, sector, theme, factor, weight, adv=1e8):
    return {"stock_code": code, "sector": sector, "theme": theme,
            "factor": factor, "weight": weight, "beta": 1.0, "adv": adv}


def test_aggregator_basic():
    pos = [_pos("A", "Tech", "AI", "AI", 0.1),
           _pos("B", "Tech", "AI", "AI", 0.1),
           _pos("C", "Bank", "Bank", "Bank", 0.1)]
    r = portfolio_risk_aggregator(pos)
    assert r["gross_exposure"] == 0.3
    assert r["sector_exposure"]["Tech"] == 0.6667
    assert r["crowding_risk"] == 0.6667
    assert r["correlation_risk"]["nominal_exposure"] == 0.3


def test_aggregator_var_es():
    import numpy as np
    pos = [_pos("A", "Tech", "AI", "AI", 0.5),
           _pos("B", "Bank", "Bank", "Bank", 0.5)]
    returns = np.array([[0.01, -0.02], [-0.03, -0.04], [0.02, 0.01]])
    r = portfolio_risk_aggregator(pos, returns_matrix=returns)
    assert r["var95"] is not None
    assert r["expected_shortfall"] is not None
