# coding: utf-8
"""Regime Transition Engine 测试（41 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.market.transition import (detect_transitions, early_warning,
                                        regime_persistence,
                                        threshold_adjustments,
                                        transition_probability,
                                        transition_speed)


def _series():
    return [("2026-01-01", "Bull"), ("2026-01-08", "Bull"),
            ("2026-01-15", "Bull"), ("2026-01-22", "Sideway"),
            ("2026-01-29", "Sideway"), ("2026-02-05", "Bear"),
            ("2026-02-12", "Bear")]


def test_detect_transitions():
    ts = detect_transitions(_series())
    assert len(ts) == 2
    assert ts[0]["from"] == "Bull" and ts[0]["to"] == "Sideway"
    assert ts[0]["confidence"] > 0


def test_probability_speed_persistence():
    s = _series()
    assert 0 < transition_probability(s) <= 1.0
    assert transition_speed(s) >= 2
    p = regime_persistence(s)
    assert p["current_regime"] == "Bear"
    assert p["persisted_periods"] == 2


def test_early_warning():
    ew = early_warning(_series(), warn_flip_rate=0.2)
    assert ew["early_warning"] is True
    assert ew["warnings"]


def test_threshold_adjustments():
    adj = threshold_adjustments("Bull", "Bear", _series())
    assert adj["risk_budget_scale"] < 1.0
    assert adj["entry_threshold_up"] > 1.0
    assert adj["add_threshold_up"] > 1.0
    assert adj["exit_sensitivity_up"] > 1.0
    # 稳定状态 → 无调整
    adj2 = threshold_adjustments("Bull", "Bull")
    assert adj2["risk_budget_scale"] == 1.0
