# coding: utf-8
"""FSM-2 状态转换测试"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.fusion.mtf_fsm import next_mtf_state


def test_state_transition():
    state, method = next_mtf_state("BULLISH_CONFIRMED",
                                   "STRUCTURAL_BULLISH", "Improving", "Breakout")
    assert state == "BULLISH_CONFIRMED"


def test_downgrade_on_breakdown():
    state, _ = next_mtf_state("BULLISH_CONFIRMED",
                              "STRUCTURAL_BULLISH", "Deteriorating", "Breakdown")
    assert state == "BULLISH_WARNING"  # 结构性强势下的战术预警，禁止清仓级输出


def test_never_bearish_from_bullish():
    # 多头结构 + 周线破位 → 只能是 BULLISH_WARNING，绝不 BEARISH_CONFIRMED
    assert next_mtf_state("BULLISH_CONFIRMED",
                          "STRUCTURAL_ACCUMULATION", "Deteriorating", "Breakdown")[0] \
        == "BULLISH_WARNING"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_mtf_fsm 全部通过 ✅")
