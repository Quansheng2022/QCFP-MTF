# coding: utf-8
"""Market Opportunity Regime 测试（71 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.market.opportunity_regime import market_opportunity_regime


def test_high_opportunity():
    r = market_opportunity_regime(opportunity_share=0.9, wave_hit_rate=0.8,
                                  breadth=0.8, permission_strength=0.9)
    assert r.level == 4
    assert r.capital_aggression == 1.0


def test_low_opportunity_defensive():
    r = market_opportunity_regime(opportunity_share=0.1, wave_hit_rate=0.2,
                                  breadth=0.2, permission_strength=0.1)
    assert r.level == 0
    assert r.capital_aggression <= 0.1


def test_risk_off_always_defensive():
    r = market_opportunity_regime(opportunity_share=0.9, risk_off=True)
    assert r.level == 0
    assert r.label == "防御"


def test_normal():
    r = market_opportunity_regime(opportunity_share=0.5, wave_hit_rate=0.5,
                                  breadth=0.5, permission_strength=0.5)
    assert r.level == 2
    assert r.label == "正常"
