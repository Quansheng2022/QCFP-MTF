# coding: utf-8
"""FSM-1 季度结构状态机 + Core Score（State-First, Score-Second）

实现说明：
- 规格书 6 种状态的 C/F/P 组合即为直接映射表；
- 规格书 8 条转换规则的"目标状态"与对应组合的直接映射一致（单元测试验证），
  因此直接映射即覆盖全部转换；对未定义的组合采取保守"保持上一状态"，
  避免低证据组合引起状态跳跃；
- F 缺失（2021 前）走 C+P 降级映射，只输出 A- 级结论。
"""

from typing import Optional, Tuple

STATE_MAP = {
    ("C↑", "F↑", "P↑"): "STRUCTURAL_BULLISH",
    ("C↑", "F↑", "P→"): "STRUCTURAL_ACCUMULATION",
    ("C↑", "F↓", "P↑"): "STRUCTURAL_DIVERGENCE",
    ("C↓", "F↓", "P↑"): "STRUCTURAL_DISTRIBUTION",
    ("C↓", "F↓", "P↓"): "STRUCTURAL_DECLINE",
    ("C↓", "F↑", "P↓"): "STRUCTURAL_BOTTOM_CANDIDATE",
}

# 恢复路径（敏感性实验用，默认关闭）：C 平向但 F、P 转好时允许退出退潮
RECOVERY_STATES = {
    ("C→", "F↑", "P↑"): "STRUCTURAL_ACCUMULATION",
    ("C→", "F↑", "P→"): "STRUCTURAL_ACCUMULATION",
    ("C→", "F↑", "P↓"): "STRUCTURAL_BOTTOM_CANDIDATE",
}

# 规格书 8 条转换规则：(当前状态, 新季度C/F/P, 目标状态)
TRANSITIONS = [
    ("STRUCTURAL_ACCUMULATION", ("C↑", "F↑", "P↑"), "STRUCTURAL_BULLISH"),
    ("STRUCTURAL_BULLISH", ("C↓", "F↓", "P↑"), "STRUCTURAL_DISTRIBUTION"),
    ("STRUCTURAL_BULLISH", ("C↑", "F↓", "P↑"), "STRUCTURAL_DIVERGENCE"),
    ("STRUCTURAL_DIVERGENCE", ("C↓", "F↓", "P↓"), "STRUCTURAL_DECLINE"),
    ("STRUCTURAL_DISTRIBUTION", ("C↓", "F↓", "P↓"), "STRUCTURAL_DECLINE"),
    ("STRUCTURAL_DECLINE", ("C↑", "F↑", "P→"), "STRUCTURAL_ACCUMULATION"),
    ("STRUCTURAL_DECLINE", ("C↓", "F↑", "P↓"), "STRUCTURAL_BOTTOM_CANDIDATE"),
    ("STRUCTURAL_BOTTOM_CANDIDATE", ("C↑", "F↑", "P↑"), "STRUCTURAL_BULLISH"),
]

# F 缺失时 C+P 降级映射（A- 级结论）
F_MISSING_MAP = {
    ("C↑", "P↑"): "STRUCTURAL_ACCUMULATION",
    ("C↓", "P↓"): "STRUCTURAL_DECLINE",
    ("C↑", "P↓"): "STRUCTURAL_BOTTOM_CANDIDATE",
    ("C↓", "P↑"): "STRUCTURAL_DIVERGENCE",
}

REGIME_DIRECTION = {
    "STRUCTURAL_BULLISH": "bull",
    "STRUCTURAL_ACCUMULATION": "bull",
    "STRUCTURAL_DIVERGENCE": "mixed",
    "STRUCTURAL_DISTRIBUTION": "bear",
    "STRUCTURAL_DECLINE": "bear",
    "STRUCTURAL_BOTTOM_CANDIDATE": "mixed",
    "STATE_UNDETERMINED": "unknown",
}


def resolve_regime(c_state, f_state, p_state,
                   prev_regime: Optional[str] = None,
                   recovery_paths: bool = False,
                   recovery_states: Optional[dict] = None) -> Tuple[str, str]:
    """State-First 解析状态

    Returns:
        (structural_regime, method)
        method: direct / fallback_f_missing / hold_missing_factor /
                hold_unmapped / missing_factor / unmapped
    """
    # 1) F 缺失降级映射
    if f_state == "F_UNKNOWN":
        if c_state is not None and p_state is not None:
            key = (c_state, p_state)
            if key in F_MISSING_MAP:
                return F_MISSING_MAP[key], "fallback_f_missing"
        if prev_regime and prev_regime != "STATE_UNDETERMINED":
            return prev_regime, "hold_missing_factor"
        return "STATE_UNDETERMINED", "fallback_f_missing"

    # 2) 任一因子缺失
    if c_state is None or f_state is None or p_state is None:
        if prev_regime and prev_regime != "STATE_UNDETERMINED":
            return prev_regime, "hold_missing_factor"
        return "STATE_UNDETERMINED", "missing_factor"

    # 3) 直接映射（含 8 条转换规则组合）
    key = (c_state, f_state, p_state)
    rec_map = RECOVERY_STATES if recovery_states is None else recovery_states
    if recovery_paths and key in rec_map:
        return rec_map[key], "recovery"
    if key in STATE_MAP:
        return STATE_MAP[key], "direct"

    # 4) 未定义组合：保守保持
    if prev_regime and prev_regime != "STATE_UNDETERMINED":
        return prev_regime, "hold_unmapped"
    return "STATE_UNDETERMINED", "unmapped"


def map_core_score(regime: Optional[str], settings: dict):
    """State-First：状态 → 基础分（0~100）"""
    if not regime or regime == "STATE_UNDETERMINED":
        return None
    mapping = settings.get("structural", {}).get("score_mapping", {})
    return float(mapping.get(regime, 50.0))


def regime_direction(regime: Optional[str]) -> str:
    return REGIME_DIRECTION.get(regime, "unknown")
