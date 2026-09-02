# coding: utf-8
"""Decision Compression Test 测试（85 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.evaluation.decision_compression import \
    decision_compression_test


def _full():
    return {"action_count": 9, "actions": ["TEST_BUY", "BUY", "ADD",
                                           "HOLD", "WATCH", "REDUCE",
                                           "EXIT"],
            "oos_sharpe": 0.80, "turnover": 2.0,
            "decision_flip_rate": 0.25, "user_understanding": 0.5,
            "max_drawdown": -0.12}


def test_merge_recommended():
    full = _full()
    compressed = {"action_count": 6, "actions": ["NO_RISK", "TEST",
                                                 "HOLD", "ADD",
                                                 "REDUCE", "EXIT"],
                  "oos_sharpe": 0.79, "turnover": 1.4,
                  "decision_flip_rate": 0.15,
                  "user_understanding": 0.8,
                  "max_drawdown": -0.13}
    r = decision_compression_test(full, compressed)
    assert r["verdict"] == "MERGE_RECOMMENDED"
    assert r["action_reduced"] is True
    assert r["worse_metrics"] == []


def test_keep_full_when_worse():
    full = _full()
    compressed = {"action_count": 5, "oos_sharpe": 0.30,
                  "turnover": 2.5, "decision_flip_rate": 0.40,
                  "user_understanding": 0.5, "max_drawdown": -0.30}
    r = decision_compression_test(full, compressed)
    assert r["verdict"] == "KEEP_FULL"
    assert "oos_sharpe" in r["worse_metrics"]


def test_review_when_actions_not_reduced():
    full = _full()
    compressed = {"action_count": 9, "oos_sharpe": 0.80,
                  "turnover": 2.0, "decision_flip_rate": 0.25,
                  "user_understanding": 0.5, "max_drawdown": -0.12}
    r = decision_compression_test(full, compressed)
    assert r["verdict"] == "REVIEW"
    assert r["action_reduced"] is False
