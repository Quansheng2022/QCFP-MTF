# coding: utf-8
"""Position Sizing Engine 2.0 测试（25 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.optimal_position import optimal_position, \
    position_from_components


def test_optimal_position_chain():
    r = optimal_position(edge=0.10, risk=0.05, confidence=0.8,
                         max_allowed=0.12, liquidity_scale=0.9,
                         portfolio_scale=0.8)
    assert r["maximum_allowed"] == 0.12
    assert r["executable_position"] <= 0.12
    assert r["binding"] in ("MAX_ALLOWED", "LIQUIDITY", "RISK_OPTIMAL")


def test_higher_confidence_larger_position():
    low = optimal_position(0.10, 0.05, 0.4, 0.5)
    high = optimal_position(0.10, 0.05, 0.9, 0.5)
    assert high["risk_optimal"] > low["risk_optimal"]


def test_max_allowed_cap():
    r = optimal_position(edge=0.5, risk=0.01, confidence=1.0,
                         max_allowed=0.05)
    assert r["executable_position"] <= 0.05
    assert r["binding"] == "MAX_ALLOWED"


def test_position_from_components():
    r = position_from_components(0.10, 0.05, 0.8, 0.10)
    assert "executable_position" in r
