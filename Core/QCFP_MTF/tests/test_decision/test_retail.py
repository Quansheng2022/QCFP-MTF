# coding: utf-8
"""散户决策层（红黄绿灯 + 六态阶梯 + A/B 池）单元测试"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.decision.retail import (classify_pool, retail_action,
                                      retail_position_band, traffic_light)


def _row(**kw):
    base = {
        "mtf_regime": "BULLISH_STABLE", "structural_regime": "STRUCTURAL_BULLISH",
        "monthly_behavior_state": "Improving", "tactical_signal": "Consolidation",
        "risk_level": "Medium", "des_score": 2, "des_band": "WATCH",
        "chip_stability_confidence": "High", "market_context": "neutral",
        "q_position_52w": 0.45, "f_state": "F↑",
    }
    base.update(kw)
    return base


def test_traffic_light():
    assert traffic_light(_row()) == "GREEN"
    assert traffic_light(_row(mtf_regime="BEARISH_CONFIRMED")) == "RED"
    assert traffic_light(_row(risk_level="Extreme")) == "RED"
    assert traffic_light(_row(des_score=7)) == "RED"
    assert traffic_light(_row(mtf_regime="BULLISH_WARNING")) == "YELLOW"
    assert traffic_light(_row(mtf_regime="BEARISH_RECOVERY_CANDIDATE")) == "YELLOW"


def test_retail_action_ladder():
    assert retail_action(_row()) == "HOLD"
    assert retail_action(_row(mtf_regime="BULLISH_CONFIRMED",
                              tactical_signal="Breakout")) == "BUILD"
    assert retail_action(_row(mtf_regime="BULLISH_WARNING")) == "REDUCE"
    assert retail_action(_row(mtf_regime="BEARISH_RECOVERY_CANDIDATE",
                              risk_level="Medium")) == "TEST"
    assert retail_action(_row(risk_level="Extreme")) == "EXIT"
    assert retail_action(_row(des_score=8)) == "EXIT"
    assert retail_action(_row(mtf_regime="BEARISH_CONFIRMED")) == "EXIT"


def test_retail_position_band_no_100pct_default():
    assert retail_position_band(_row(risk_level="Extreme"), DEFAULT_SETTINGS) == "0%"
    assert retail_position_band(_row(risk_level="High"), DEFAULT_SETTINGS) == "0%~20%"
    assert retail_position_band(_row(mtf_regime="BULLISH_STABLE"),
                                DEFAULT_SETTINGS) == "50%~70%"
    assert retail_position_band(_row(mtf_regime="BULLISH_CONFIRMED",
                                     market_context="neutral"),
                                DEFAULT_SETTINGS) == "60%~80%"
    assert retail_position_band(_row(mtf_regime="BULLISH_CONFIRMED",
                                     market_context="risk_on"),
                                DEFAULT_SETTINGS) == "80%~100%"


def test_classify_pool():
    a = _row()
    assert classify_pool(a, DEFAULT_SETTINGS) == "A"
    b = _row(structural_regime="STRUCTURAL_BOTTOM_CANDIDATE",
             q_position_52w=0.08, tactical_signal="Breakout",
             risk_level="Medium")
    assert classify_pool(b, DEFAULT_SETTINGS) == "B"
    # B 池不是立即买：52W 不低或风险 High → 不入池
    assert classify_pool(_row(structural_regime="STRUCTURAL_DECLINE",
                              q_position_52w=0.5,
                              tactical_signal="Breakout"), DEFAULT_SETTINGS) is None


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_retail 全部通过 ✅")
