# coding: utf-8
"""Strategy Kill Criteria 测试（96 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.safety.strategy_kill import STRATEGY_KILL_CRITERIA, \
    classify_control_event, strategy_kill_check


def test_no_criteria_production():
    r = strategy_kill_check({c: False for c in STRATEGY_KILL_CRITERIA})
    assert r["verdict"] == "PRODUCTION"
    assert r["halt_new_decisions"] is False


def test_any_criteria_suspends():
    criteria = {c: False for c in STRATEGY_KILL_CRITERIA}
    criteria["pit_integrity_failure"] = True
    r = strategy_kill_check(criteria)
    assert r["verdict"] == "SUSPENDED"
    assert r["active_criteria"] == ["pit_integrity_failure"]
    assert r["halt_new_decisions"] is True


def test_classify_three_kinds():
    assert classify_control_event("TRADE_EXIT")["scope"] == "单只股票/仓位"
    assert classify_control_event("STRATEGY_SUSPEND")["scope"] == \
        "整个策略版本"
    assert classify_control_event("SYSTEM_HALT")["scope"] == "系统本身"
    assert classify_control_event("UNKNOWN_KIND")["classified"] is False
