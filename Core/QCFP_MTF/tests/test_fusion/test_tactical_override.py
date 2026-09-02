# coding: utf-8
"""方案 B 战术试多（空头结构轻仓）测试"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.decision.position_sizing import effective_position_cqs
from QCFP_MTF.fusion.mtf_alignment import align_mtf


def test_tactical_override_allows_warning_at_extreme_low():
    rg, method = align_mtf("STRUCTURAL_DECLINE", "Deteriorating", "Breakout",
                           tactical_override=True, position_52w=0.05,
                           max_52w_position=0.15)
    assert rg == "BULLISH_WARNING" and method == "tactical_override"


def test_tactical_override_blocked_by_52w():
    rg, method = align_mtf("STRUCTURAL_DECLINE", "Deteriorating", "Breakout",
                           tactical_override=True, position_52w=0.5,
                           max_52w_position=0.15)
    assert method != "tactical_override"


def test_tactical_override_requires_breakout():
    rg, method = align_mtf("STRUCTURAL_DECLINE", "Stable", "Consolidation",
                           tactical_override=True, position_52w=0.05,
                           max_52w_position=0.15)
    assert method != "tactical_override"


def test_tactical_override_any_trigger_when_empty():
    for trigger in ("Breakout", "Pullback", "Consolidation"):
        rg, method = align_mtf("STRUCTURAL_DECLINE", "Improving", trigger,
                               tactical_override=True, position_52w=0.05,
                               max_52w_position=0.15, min_trigger=())
        assert rg == "BULLISH_WARNING"
        assert method == "tactical_override"


def test_override_disabled_default():
    rg, method = align_mtf("STRUCTURAL_DECLINE", "Improving", "Breakout")
    assert method != "tactical_override"


def test_position_cqs_scaling():
    pos = effective_position_cqs("BULLISH_WARNING", "High", DEFAULT_SETTINGS,
                                 catalyst_score=3, tactical_override=True)
    assert abs(pos - 0.35) < 1e-9
    pos_low = effective_position_cqs("BULLISH_WARNING", "Extreme", DEFAULT_SETTINGS,
                                     catalyst_score=-2, tactical_override=True)
    assert abs(pos_low - 0.05) < 1e-9
    assert effective_position_cqs("BULLISH_STABLE", "Low", DEFAULT_SETTINGS) == 0.75


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_tactical_override 全部通过 ✅")
