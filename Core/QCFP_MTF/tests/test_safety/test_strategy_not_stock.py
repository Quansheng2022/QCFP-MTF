# coding: utf-8
"""Strategy Kill 整策略级判定测试（新 96 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.safety.strategy_kill import STRATEGY_KILL_CRITERIA, \
    strategy_not_stock_answer


def test_strategy_suspended_answer():
    criteria = {c: False for c in STRATEGY_KILL_CRITERIA}
    criteria["pit_integrity_failure"] = True
    r = strategy_not_stock_answer(criteria)
    assert r["strategy_level"] is True
    assert r["verdict"] == "STRATEGY_SUSPENDED"
    assert "不是单只股票错了" in r["answer"]


def test_strategy_active_answer():
    criteria = {c: False for c in STRATEGY_KILL_CRITERIA}
    r = strategy_not_stock_answer(criteria)
    assert r["strategy_level"] is False
    assert r["verdict"] == "STRATEGY_ACTIVE"
