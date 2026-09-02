# coding: utf-8
"""机构行为过滤器 + Retail Position FSM 单元测试（V24）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.decision.institutional_filter import (institutional_pressure,
                                                    institutional_state)
from QCFP_MTF.decision.institutional_permission import evaluate_institutional_permission
from QCFP_MTF.decision.retail_fsm import build_fsm_timeline, chase_filter, next_state


def test_institutional_state_and_permission():
    assert institutional_state("C↑", "F↑", "P↑") == "ACCUMULATION"
    assert evaluate_institutional_permission(
        institutional_state_name="ACCUMULATION", pressure=2,
        persistence=2).permission == "STRONG_ALLOW"
    assert evaluate_institutional_permission(
        institutional_state_name="ACCUMULATION", pressure=1,
        persistence=2).permission == "ALLOW"
    assert institutional_state("C→", "F↑", "P↓") == "RECOVERY"
    assert evaluate_institutional_permission(
        institutional_state_name="RECOVERY", pressure=1,
        persistence=1).permission == "TEST"
    assert institutional_state("C↓", "F↓", "P↓") == "CAPITULATION"
    assert evaluate_institutional_permission(
        institutional_state_name="CAPITULATION", pressure=-2,
        persistence=0).permission == "BLOCK"
    assert institutional_pressure("C↑", "F↑") == 2
    assert institutional_pressure("C↓", "F↓") == -2


def test_hard_exit_overrides_bullish():
    # STRUCTURAL_BULLISH + DES≥7 → Hard Exit（不是 REDUCE）
    row = {"institutional_permission": "ALLOW", "risk_level": "Medium",
           "des_score": 8, "daily_state": "DAILY_NEUTRAL",
           "tactical_signal": "Consolidation", "q_position_52w": 0.3}
    assert next_state("HOLDING", row, DEFAULT_SETTINGS) == "EXITING"


def test_fsm_lifecycle_with_cooldown():
    allow = {"institutional_permission": "ALLOW", "risk_level": "Medium",
             "des_score": 1, "daily_state": "DAILY_BREAKOUT",
             "tactical_signal": "Breakout", "q_position_52w": 0.3}
    rows = [allow] * 2 + [
        {**allow, "des_score": 8},        # hard exit
        {**allow},                         # COOLDOWN（第 1 周）
        {**allow},                         # COOLDOWN（第 2 周）
        {**allow},                         # 冷却结束 → 重新资格 → TESTING
    ]
    states = [s for s, _ in build_fsm_timeline(rows, DEFAULT_SETTINGS)]
    assert states[0] == "TESTING"
    assert states[1] == "BUILDING"
    assert states[2] == "EXITING"
    assert states[3] == "COOLDOWN" and states[4] == "COOLDOWN"
    assert states[5] == "TESTING"         # 2 周冷却结束后重新资格 → TEST


def test_chase_filter():
    row = {"daily_state": "DAILY_BREAKOUT", "q_position_52w": 0.8}
    assert chase_filter(row, DEFAULT_SETTINGS) is True
    row["q_position_52w"] = 0.3
    assert chase_filter(row, DEFAULT_SETTINGS) is False


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_institutional_filter 全部通过 ✅")
