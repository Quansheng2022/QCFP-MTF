# coding: utf-8
"""Portfolio Decision Ledger 测试（44 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.portfolio.portfolio_ledger import PortfolioLedger, \
    record_portfolio_decision


def test_record_and_query():
    led = PortfolioLedger()
    record_portfolio_decision(
        led, "P-001", positions_before={"A": 0.0, "B": 0.05},
        positions_after={"A": 0.05, "B": 0.0},
        rejected=[{"stock_code": "C", "reason": "RANK_LOW"}],
        replacements=[{"sold": "B", "bought": "A", "reason": "SWITCH"}])
    assert led.latest().gross_exposure == 0.05
    assert led.why_not_bought("C")[0]["reason"] == "RANK_LOW"
    assert led.why_sold("B")
    # append-only
    record_portfolio_decision(led, "P-002",
                              positions_before={"A": 0.05},
                              positions_after={"A": 0.02})
    assert len(led.records) == 2


def test_why_sold_position_reduction():
    led = PortfolioLedger()
    record_portfolio_decision(
        led, "P-003", positions_before={"B": 0.08},
        positions_after={"B": 0.03})
    sales = led.why_sold("B")
    assert sales and sales[0]["before"] == 0.08
