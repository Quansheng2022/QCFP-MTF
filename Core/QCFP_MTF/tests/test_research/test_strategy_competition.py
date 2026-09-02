# coding: utf-8
"""Strategy Competition 测试（48 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.research.strategy_competition import strategy_competition


def _strategies():
    return {
        "A_full": {"sharpe": 1.31, "return": 0.21, "mdd": -0.16,
                   "turnover": 1.0, "capacity": 0.8, "robustness": 0.9,
                   "decision_quality": 0.85},
        "B_simplified": {"sharpe": 1.25, "return": 0.19, "mdd": -0.17,
                         "turnover": 0.8, "capacity": 0.9,
                         "robustness": 0.95, "decision_quality": 0.9},
        "C_weak": {"sharpe": 0.6, "return": 0.08, "mdd": -0.30,
                   "turnover": 2.0, "capacity": 0.3, "robustness": 0.2,
                   "decision_quality": 0.4},
    }


def test_strategy_competition():
    r = strategy_competition(_strategies())
    # 平衡评分下简化策略胜出（容量/稳健性/决策质量补偿 Sharpe）
    assert r["champion"] == "B_simplified"
    assert r["promotion_candidate"] == "B_simplified"
    assert "A_full" in r["challengers"]
    assert "C_weak" in r["retired_candidates"]
