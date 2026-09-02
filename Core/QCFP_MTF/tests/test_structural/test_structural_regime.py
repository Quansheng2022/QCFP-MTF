# coding: utf-8
"""FSM-1 状态机 + Core Score 测试"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.structural.structural_regime import (RECOVERY_STATES, STATE_MAP,
                                                   TRANSITIONS,
                                                   map_core_score,
                                                   regime_direction,
                                                   resolve_regime)


def test_direct_mapping_all_states():
    for combo, state in STATE_MAP.items():
        rg, method = resolve_regime(*combo)
        assert rg == state and method == "direct"


def test_all_transitions_equivalent_to_direct_map():
    # 规格书 8 条转换规则的目标 == 直接映射目标
    for prev, combo, target in TRANSITIONS:
        assert STATE_MAP[combo] == target
        rg, _ = resolve_regime(*combo, prev_regime=prev)
        assert rg == target


def test_f_missing_fallback():
    cases = [
        (("C↑", "F_UNKNOWN", "P↑"), "STRUCTURAL_ACCUMULATION"),
        (("C↓", "F_UNKNOWN", "P↓"), "STRUCTURAL_DECLINE"),
        (("C↑", "F_UNKNOWN", "P↓"), "STRUCTURAL_BOTTOM_CANDIDATE"),
        (("C↓", "F_UNKNOWN", "P↑"), "STRUCTURAL_DIVERGENCE"),
    ]
    for (c, f, p), expected in cases:
        rg, method = resolve_regime(c, f, p)
        assert rg == expected and method == "fallback_f_missing"


def test_f_missing_undefined():
    rg, _ = resolve_regime("C→", "F_UNKNOWN", "P→")
    assert rg == "STATE_UNDETERMINED"


def test_unmapped_holds_prev():
    rg, method = resolve_regime("C→", "F→", "P→", prev_regime="STRUCTURAL_BULLISH")
    assert rg == "STRUCTURAL_BULLISH" and method == "hold_unmapped"


def test_missing_factor_holds_prev():
    rg, method = resolve_regime(None, "F↑", "P↑", prev_regime="STRUCTURAL_DECLINE")
    assert rg == "STRUCTURAL_DECLINE" and method == "hold_missing_factor"


def test_core_score_state_first():
    assert map_core_score("STRUCTURAL_BULLISH", DEFAULT_SETTINGS) == 85.0
    assert map_core_score("STATE_UNDETERMINED", DEFAULT_SETTINGS) is None


def test_regime_direction():
    assert regime_direction("STRUCTURAL_BULLISH") == "bull"
    assert regime_direction("STRUCTURAL_DECLINE") == "bear"
    assert regime_direction("STRUCTURAL_DIVERGENCE") == "mixed"


def test_recovery_paths_off_by_default():
    # 默认不启用恢复路径：C→F↑P↑ 仍按未定义组合处理（保持前状态）
    rg, method = resolve_regime("C→", "F↑", "P↑", prev_regime="STRUCTURAL_DECLINE")
    assert rg == "STRUCTURAL_DECLINE" and method == "hold_unmapped"


def test_recovery_paths_enabled():
    for combo, state in RECOVERY_STATES.items():
        rg, method = resolve_regime(*combo, recovery_paths=True)
        assert rg == state and method == "recovery"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_structural_regime 全部通过 ✅")
