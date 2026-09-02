# coding: utf-8
"""Regime × Strategy Matrix 测试（37 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.evaluation.regime_matrix import regime_strategy_matrix


def _trades():
    return [
        {"regime": "Bull", "permission": "ALLOW", "wave_strength": 0.8,
         "net_return": 0.10},
        {"regime": "Bull", "permission": "ALLOW", "wave_strength": 0.7,
         "net_return": 0.05},
        {"regime": "Bear", "permission": "WATCH", "wave_strength": 0.2,
         "net_return": -0.04},
        {"regime": "Transition", "permission": "ALLOW",
         "wave_strength": 0.9, "net_return": -0.02},
    ]


def test_regime_matrix():
    r = regime_strategy_matrix(_trades())
    assert r["matrix"]["Bull"]["trades"] == 2
    assert r["matrix"]["Bull"]["win_rate"] == 1.0
    assert r["matrix"]["Bear"]["mdd"] < 0
    assert "interaction" in r
    # ALLOW+Bull+STRONG 交互
    assert any(k[0] == "ALLOW" and k[1] == "Bull"
               for k in r["interaction"])
