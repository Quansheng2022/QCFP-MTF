# coding: utf-8
"""Portfolio Rebalancing Governance 测试（66 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.portfolio.rebalancing import rebalance_decision


def test_within_band_no_trade():
    r = rebalance_decision(0.05, 0.048, rebalance_band=0.01)
    assert r["trade"] is False
    assert r["reason"] == "WITHIN_BAND"


def test_below_min_trade_size():
    r = rebalance_decision(0.06, 0.05, rebalance_band=0.001,
                           min_trade_size=0.02)
    assert r["trade"] is False
    assert r["reason"] == "BELOW_MIN_TRADE_SIZE"


def test_cooldown_blocks():
    r = rebalance_decision(0.10, 0.05, rebalance_band=0.001,
                           last_trade_date="2026-08-26",
                           today="2026-08-27", cooldown_days=5)
    assert r["trade"] is False
    assert r["reason"] == "COOLDOWN"


def test_rebalance_ok():
    r = rebalance_decision(0.10, 0.05, rebalance_band=0.001,
                           min_expected_benefit=0.001,
                           transaction_cost=0.001)
    assert r["trade"] is True
    assert r["action"] == "ADD"
