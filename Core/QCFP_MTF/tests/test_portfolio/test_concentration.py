# coding: utf-8
"""Portfolio Concentration Governor 测试（77 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.portfolio.concentration import effective_concentration


def _pos(code, sector, theme, weight, beta=1.0):
    return {"stock_code": code, "sector": sector, "theme": theme,
            "weight": weight, "beta": beta}


def test_diversified_no_restriction():
    pos = [_pos("A", "Bank", "t1", 0.1, beta=1.5),
           _pos("B", "Tech", "t2", 0.1, beta=0.8),
           _pos("C", "Energy", "t3", 0.1, beta=1.1)]
    r = effective_concentration(pos)
    assert r["restricted"] is False
    assert r["concentration_scale"] == 1.0


def test_hidden_concentration_restricted():
    pos = [_pos("A", "Tech", "AI", 0.1, beta=1.0),
           _pos("B", "Tech", "AI", 0.1, beta=1.0),
           _pos("C", "Tech", "AI", 0.1, beta=1.0)]
    r = effective_concentration(pos)
    assert r["max_sector"] == 1.0
    assert r["restricted"] is True
    assert r["concentration_scale"] < 1.0
    assert any("SECTOR_CONCENTRATED" in f for f in r["flags"])
    assert any("BETA_HOMOGENEOUS" in f for f in r["flags"])
