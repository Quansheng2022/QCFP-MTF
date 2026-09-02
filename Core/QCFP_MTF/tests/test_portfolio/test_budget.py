# coding: utf-8
"""Portfolio Exposure Budget 测试（21 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.portfolio.budget import (budget_to_md, portfolio_budget,
                                       portfolio_budget_cap)


def test_portfolio_budget_basic():
    b = portfolio_budget(
        gross_exposure=0.4, sector_exposure={"Tech": 0.2, "Bank": 0.2},
        theme_exposure={"AI": 0.1}, risk_budget=0.10)
    assert b.gross_exposure == 0.4
    assert b.available_new_risk > 0
    assert b.flags == ()


def test_portfolio_budget_flags_concentration():
    b = portfolio_budget(
        gross_exposure=0.6, sector_exposure={"Tech": 0.55},
        theme_exposure={"AI": 0.6}, max_sector=0.25, max_theme=0.15)
    assert any("SECTOR_OVER" in f for f in b.flags)
    assert any("THEME_OVER" in f for f in b.flags)
    # 超限 → 可用新增风险收缩
    assert b.available_new_risk < 0.10


def test_portfolio_budget_cap_chain():
    b = portfolio_budget(
        gross_exposure=0.5, risk_budget=0.10, single_stock_cap=0.08,
        liquidity_cap=0.8)
    cap = portfolio_budget_cap(b)
    assert cap <= 0.08
    assert cap <= b.available_new_risk


def test_budget_to_md():
    b = portfolio_budget(gross_exposure=0.3)
    assert "Portfolio Exposure Budget" in budget_to_md(b)
