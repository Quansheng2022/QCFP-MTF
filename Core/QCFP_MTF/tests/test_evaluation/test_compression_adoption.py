# coding: utf-8
"""Decision Compression 采用测试（新 85 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.evaluation.decision_compression import \
    RECOMMENDED_COMPRESSED_TAXONOMY, compression_adoption, \
    decision_compression_test, recommended_compressed_taxonomy


def _full():
    return {"action_count": 7, "actions": ["TEST_BUY", "BUY", "ADD",
                                           "HOLD", "WATCH", "REDUCE",
                                           "EXIT"],
            "oos_sharpe": 0.80, "turnover": 2.0,
            "decision_flip_rate": 0.25, "user_understanding": 0.5,
            "max_drawdown": -0.12}


def test_recommended_taxonomy():
    r = recommended_compressed_taxonomy(_full()["actions"])
    assert r["compressed_actions"] == \
        list(RECOMMENDED_COMPRESSED_TAXONOMY)
    assert r["reduction"] == 2


def test_adopt_when_better():
    full = _full()
    compressed = {"action_count": 5, "actions": list(
        RECOMMENDED_COMPRESSED_TAXONOMY),
        "oos_sharpe": 0.79, "turnover": 1.4,
        "decision_flip_rate": 0.15, "user_understanding": 0.8,
        "max_drawdown": -0.13}
    t = decision_compression_test(full, compressed)
    r = compression_adoption(t)
    assert r["adopt"] is True
    assert r["verdict"] == "ADOPT_COMPRESSED"


def test_keep_when_worse():
    full = _full()
    compressed = {"action_count": 5, "oos_sharpe": 0.30,
                  "turnover": 2.5, "decision_flip_rate": 0.40,
                  "user_understanding": 0.5, "max_drawdown": -0.30}
    t = decision_compression_test(full, compressed)
    r = compression_adoption(t)
    assert r["adopt"] is False
