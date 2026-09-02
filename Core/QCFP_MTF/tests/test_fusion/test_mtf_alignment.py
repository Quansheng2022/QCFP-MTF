# coding: utf-8
"""MTF 对齐矩阵 + 兜底 + 不越权测试"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.fusion.mtf_alignment import (ALIGNMENT_MATRIX, _assert_no_overrule,
                                           align_mtf, structure_behavior_alignment)


def test_matrix_12_rows():
    for key, state in ALIGNMENT_MATRIX.items():
        rg, method = align_mtf(*key)
        assert rg == state and method == "matrix"


def test_fallback_bullish_family():
    assert align_mtf("STRUCTURAL_BULLISH", "Stable", "Pullback")[0] == "BULLISH_STABLE"
    # 兜底规则：多头族仅 Deteriorating+Breakdown 才 WARNING，其余 STABLE
    assert align_mtf("STRUCTURAL_BULLISH", "Deteriorating", "Consolidation")[0] == "BULLISH_STABLE"
    assert align_mtf("STRUCTURAL_ACCUMULATION", "Stable", "Breakout")[0] == "BULLISH_STABLE"


def test_fallback_bearish_family():
    assert align_mtf("STRUCTURAL_DECLINE", "Improving", "Breakout")[0] == "BEARISH_RECOVERY_CANDIDATE"
    assert align_mtf("STRUCTURAL_DECLINE", "Stable", "Consolidation")[0] == "BEARISH_CONFIRMED"
    assert align_mtf("STRUCTURAL_DISTRIBUTION", "Improving", "Breakout")[0] == "BEARISH_RECOVERY_CANDIDATE"


def test_fallback_divergence_and_bottom():
    assert align_mtf("STRUCTURAL_DIVERGENCE", "Improving", "Breakout")[0] == "BULLISH_WARNING"
    assert align_mtf("STRUCTURAL_BOTTOM_CANDIDATE", "Stable", "Consolidation")[0] == "BULLISH_WARNING"


def test_no_overrule_bullish_structure():
    # 多头结构禁止 BEARISH_CONFIRMED
    try:
        align_mtf("STRUCTURAL_BULLISH", "Deteriorating", "Breakdown")
        # 该组合按矩阵应输出 BULLISH_WARNING，不触发
    except ValueError:
        pass
    assert align_mtf("STRUCTURAL_BULLISH", "Deteriorating", "Breakdown")[0] == "BULLISH_WARNING"


def test_no_overrule_bearish_structure():
    raised = False
    try:
        _assert_no_overrule("STRUCTURAL_DECLINE", "BULLISH_CONFIRMED")
    except ValueError:
        raised = True
    assert raised
    # 兜底保证空头族永不输出多头状态
    assert align_mtf("STRUCTURAL_DECLINE", "Improving", "Breakout")[0] == "BEARISH_RECOVERY_CANDIDATE"


def test_data_insufficient():
    assert align_mtf("STATE_UNDETERMINED", "Improving", "Breakout")[0] == "DATA_INSUFFICIENT"
    assert align_mtf(None, "Stable", "Consolidation")[0] == "DATA_INSUFFICIENT"


def test_structure_behavior_divergence():
    assert structure_behavior_alignment("STRUCTURAL_BULLISH", "Deteriorating") == "Divergence"
    assert structure_behavior_alignment("STRUCTURAL_DECLINE", "Improving") == "Divergence"
    assert structure_behavior_alignment("STRUCTURAL_BULLISH", "Improving") == "Aligned"
    assert structure_behavior_alignment(None, "Improving") == "Unknown"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_mtf_alignment 全部通过 ✅")
