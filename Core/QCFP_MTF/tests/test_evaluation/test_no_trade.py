# coding: utf-8
"""No-Trade Quality Score 测试（96 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.evaluation.no_trade import no_trade_quality


def _decisions():
    return [
        {"traded": True, "net_return": 0.12},     # Correct Trade
        {"traded": True, "net_return": -0.06},    # False Trade
        {"traded": False, "net_return": -0.15},   # Correct No-Trade
        {"traded": False, "net_return": 0.30},    # False No-Trade
        {"traded": True, "net_return": 0.05},     # Correct Trade
    ]


def test_no_trade_quality():
    r = no_trade_quality(_decisions())
    cm = r["confusion_matrix"]
    assert cm["correct_trade"] == 2
    assert cm["false_trade"] == 1
    assert cm["correct_no_trade"] == 1
    assert cm["false_no_trade"] == 1
    assert r["avoided_loss"] == 0.15
    assert r["missed_gain"] == 0.30


def test_no_trade_score_rewards_correct_blocks():
    good = no_trade_quality([{"traded": False, "net_return": -0.10}])
    bad = no_trade_quality([{"traded": False, "net_return": 0.20}])
    assert good["no_trade_score"] > bad["no_trade_score"]
