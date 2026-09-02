# coding: utf-8
"""Decision Confidence / Position Multiplier 测试（57 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.confidence import confidence_position_multiplier, \
    evaluate_confidence


def test_confidence_multiplier_bands():
    assert confidence_position_multiplier(0.90)["position_multiplier"] == 1.0
    assert confidence_position_multiplier(0.75)["position_multiplier"] == 0.7
    assert confidence_position_multiplier(0.60)["position_multiplier"] == 0.4
    assert confidence_position_multiplier(0.40)["position_multiplier"] == 0.1


def test_confidence_governance_clamp():
    # BLOCK → 0
    assert confidence_position_multiplier(0.90, permission="BLOCK")[
        "position_multiplier"] == 0.0
    # WATCH → ≤ 0.2
    assert confidence_position_multiplier(0.90, permission="WATCH")[
        "position_multiplier"] == 0.2
    # Governance Cap → 不放大
    r = confidence_position_multiplier(0.90, governance_cap=0.5)
    assert r["position_multiplier"] == 0.5
    assert r["governance_capped"] is True


def test_evaluate_confidence_unchanged():
    c = evaluate_confidence(institutional_state="ACCUMULATION",
                            institutional_permission="ALLOW",
                            setup_type="BREAKOUT", risk_level="Low",
                            data_quality="B", pit_grade="B")
    assert 0 <= c.score <= 100
