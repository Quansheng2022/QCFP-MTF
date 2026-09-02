# coding: utf-8
"""Position Lifecycle Analytics 测试（15 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.evaluation.position_lifecycle import LIFECYCLE_STAGES, \
    position_lifecycle, stage_quality_stats


def _stages():
    return [
        {"stage": "ENTRY", "price": 10.0, "target": 0.02,
         "position": 0.0, "pnl": 0.0, "holding_days": 0,
         "reason": "WAVE_CONFIRM", "decision_hash": "h1"},
        {"stage": "HOLD", "price": 11.0, "target": 0.05,
         "position": 0.05, "pnl": 0.10, "holding_days": 10,
         "reason": "TREND_OK", "decision_hash": "h2"},
        {"stage": "EXIT", "price": 10.5, "target": 0.0,
         "position": 0.0, "pnl": 0.05, "holding_days": 15,
         "reason": "SIGNAL_WEAK", "decision_hash": "h3"},
    ]


def test_position_lifecycle():
    r = position_lifecycle(_stages())
    assert r["complete"] is True
    assert r["stages"]["ENTRY"]["reason"] == "WAVE_CONFIRM"
    assert r["stages"]["EXIT"]["decision_hash"] == "h3"


def test_stage_quality_stats():
    trades = [{"stages": {"ENTRY": {"pnl": 0.02},
                          "EXIT": {"pnl": 0.05}}},
              {"stages": {"ENTRY": {"pnl": -0.01},
                          "EXIT": {"pnl": -0.03}}}]
    s = stage_quality_stats(trades)
    assert s["ENTRY"]["win_rate"] == 0.5
    assert s["EXIT"]["n"] == 2


def test_stages_constant():
    assert LIFECYCLE_STAGES == ("ENTRY", "INITIAL_RISK", "ADD", "HOLD",
                                "TRIM", "EXIT", "COOLDOWN")
