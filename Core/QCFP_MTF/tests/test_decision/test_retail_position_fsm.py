# coding: utf-8
"""Retail Position FSM 正式接口测试（冻结转移 + 禁止跳跃）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.decision.retail_position_fsm import RetailDecisionContext, next_state


def _ctx(**kw):
    base = dict(institutional_permission="ALLOW", institutional_state="ACCUMULATION",
                mtf_regime="BULLISH_STABLE", weekly_signal="Consolidation",
                daily_state="DAILY_BREAKOUT", risk_level="Medium",
                des_score=1, current_position=0.0, chase_filter=False,
                hard_exit=False)
    base.update(kw)
    return RetailDecisionContext(**base)


def test_full_lifecycle():
    assert next_state("FLAT", _ctx()) == "TESTING"
    assert next_state("TESTING", _ctx(current_position=0.1)) == "BUILDING"
    assert next_state("BUILDING", _ctx(weekly_signal="Breakout",
                                       current_position=0.2)) == "HOLDING"
    assert next_state("HOLDING", _ctx(daily_state="DAILY_DISTRIBUTION",
                                      current_position=0.3)) == "TRIMMING"
    assert next_state("TRIMMING", _ctx(daily_state="DAILY_NEUTRAL",
                                       current_position=0.4)) == "HOLDING"
    assert next_state("HOLDING", _ctx(weekly_signal="Breakdown")) == "EXITING"
    assert next_state("EXITING", _ctx()) == "COOLDOWN"
    assert next_state("COOLDOWN", _ctx(cooldown_remaining=1)) == "COOLDOWN"
    assert next_state("COOLDOWN", _ctx(cooldown_remaining=0)) == "TESTING"


def test_no_state_jump():
    # 禁止 FLAT → HOLDING
    assert next_state("FLAT", _ctx(daily_state="DAILY_NEUTRAL")) == "FLAT"
    assert next_state("FLAT", _ctx()) == "TESTING"
    assert next_state("TESTING", _ctx(current_position=0.1)) == "BUILDING"


def test_hard_exit_highest_priority():
    # HARD_EXIT > BULLISH/ALLOW/BREAKOUT
    assert next_state("HOLDING", _ctx(des_score=8, daily_state="DAILY_BREAKOUT",
                                      institutional_permission="STRONG_ALLOW")) == "EXITING"
    assert next_state("FLAT", _ctx(risk_level="Extreme")) == "COOLDOWN"


def test_block_breakout_and_cooldown_breakout():
    # BLOCK + BREAKOUT → 不升级；COOLDOWN + BREAKOUT（未满）→ 仍 COOLDOWN
    assert next_state("FLAT", _ctx(institutional_permission="BLOCK")) == "FLAT"
    assert next_state("COOLDOWN", _ctx(cooldown_remaining=1)) == "COOLDOWN"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_retail_position_fsm 全部通过 ✅")
