# coding: utf-8
"""Action 生成器 + 单向门控测试"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.decision.action_generator import generate_action


def test_base_mapping():
    assert generate_action("BULLISH_CONFIRMED", "STRUCTURAL_BULLISH", "Low", DEFAULT_SETTINGS) == "BUY"
    assert generate_action("BULLISH_STABLE", "STRUCTURAL_BULLISH", "Low", DEFAULT_SETTINGS) == "HOLD"
    assert generate_action("BULLISH_WARNING", "STRUCTURAL_BULLISH", "Medium", DEFAULT_SETTINGS) == "REDUCE"
    assert generate_action("BEARISH_RECOVERY_CANDIDATE", "STRUCTURAL_BOTTOM_CANDIDATE", "High", DEFAULT_SETTINGS) == "WAIT"
    assert generate_action("BEARISH_CONFIRMED", "STRUCTURAL_DECLINE", "High", DEFAULT_SETTINGS) == "EXIT"


def test_bearish_gate_blocks_buy():
    # 空头结构即使给出 BUY 映射也被拦截为 WAIT
    assert generate_action("BULLISH_CONFIRMED", "STRUCTURAL_DECLINE", "Low", DEFAULT_SETTINGS) == "WAIT"


def test_bullish_gate_blocks_exit():
    # 多头结构禁止 EXIT：即使触发 EXIT 映射也强制降为 REDUCE（反向降级规则）
    assert generate_action("BEARISH_CONFIRMED", "STRUCTURAL_BULLISH", "High", DEFAULT_SETTINGS) == "REDUCE"


def test_extreme_forces_wait():
    assert generate_action("BULLISH_CONFIRMED", "STRUCTURAL_BULLISH", "Extreme", DEFAULT_SETTINGS) == "WAIT"


def test_insufficient_wait():
    assert generate_action("DATA_INSUFFICIENT", "STATE_UNDETERMINED", "Extreme", DEFAULT_SETTINGS) == "WAIT"
    assert generate_action("BEARISH_CONFIRMED", None, "High", DEFAULT_SETTINGS) == "WAIT"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_action_generator 全部通过 ✅")
