# coding: utf-8
"""Transferability Validation 测试（49 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.research.transferability import transferability_validation


def test_market_general():
    r = transferability_validation({
        "HK": {"sharpe": 1.2, "n_trades": 100},
        "CN": {"sharpe": 1.0, "n_trades": 80},
        "US": {"sharpe": 0.9, "n_trades": 60}},
        mechanism_structural=True)
    assert r["classification"] == "Market-General"
    assert r["transferable"] is True


def test_market_specific():
    r = transferability_validation({
        "HK": {"sharpe": 1.3, "n_trades": 100}})
    assert r["classification"] == "Market-Specific"
    assert r["transferable"] is False


def test_stock_specific():
    r = transferability_validation({
        "HK": {"sharpe": 0.2, "n_trades": 50}})
    assert r["classification"] == "Stock-Specific"
