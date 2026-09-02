# coding: utf-8
"""Module Consensus / Ensemble 测试（58 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.consensus import module_consensus


def test_consensus_high():
    c = module_consensus({"wave": 1, "trend": 1, "momentum": 1,
                          "liquidity": 1, "fsm": 1})
    assert c.band == "HIGH"
    assert c.recommend_reduce is False


def test_consensus_low_wave_strong():
    c = module_consensus({"wave": 1, "trend": -1, "momentum": -1,
                          "liquidity": -1, "fsm": 0})
    assert c.band == "LOW"
    assert c.recommend_reduce is True
    assert any("WAVE_STRONG_BUT_CONSENSUS_LOW" in r for r in c.reasons)


def test_consensus_medium():
    c = module_consensus({"wave": 1, "trend": 1, "momentum": -1,
                          "liquidity": 0, "fsm": 0})
    assert c.band == "MEDIUM"
