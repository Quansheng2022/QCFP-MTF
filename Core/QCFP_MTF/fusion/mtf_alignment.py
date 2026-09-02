# coding: utf-8
"""多周期对齐协调器（FSM-2 的判定表）

规格书 12 条矩阵 + 文档化兜底规则 + "层级不可越权"硬断言。
"""

BULLISH_FAMILY = {"STRUCTURAL_BULLISH", "STRUCTURAL_ACCUMULATION"}
BEARISH_FAMILY = {"STRUCTURAL_DECLINE", "STRUCTURAL_DISTRIBUTION"}
BULLISH_MTF = {"BULLISH_CONFIRMED", "BULLISH_STABLE", "BULLISH_WARNING"}

# 规格书 12 条精确映射
ALIGNMENT_MATRIX = {
    ("STRUCTURAL_BULLISH", "Improving", "Breakout"): "BULLISH_CONFIRMED",
    ("STRUCTURAL_BULLISH", "Improving", "Consolidation"): "BULLISH_STABLE",
    ("STRUCTURAL_BULLISH", "Stable", "Breakout"): "BULLISH_STABLE",
    ("STRUCTURAL_BULLISH", "Stable", "Consolidation"): "BULLISH_STABLE",
    ("STRUCTURAL_BULLISH", "Deteriorating", "Breakdown"): "BULLISH_WARNING",
    ("STRUCTURAL_ACCUMULATION", "Improving", "Breakout"): "BULLISH_CONFIRMED",
    ("STRUCTURAL_ACCUMULATION", "Improving", "Consolidation"): "BULLISH_STABLE",
    ("STRUCTURAL_ACCUMULATION", "Deteriorating", "Breakdown"): "BULLISH_WARNING",
    ("STRUCTURAL_DIVERGENCE", "Deteriorating", "Breakdown"): "BULLISH_WARNING",
    ("STRUCTURAL_DISTRIBUTION", "Deteriorating", "Breakdown"): "BEARISH_CONFIRMED",
    ("STRUCTURAL_DECLINE", "Deteriorating", "Breakdown"): "BEARISH_CONFIRMED",
    ("STRUCTURAL_BOTTOM_CANDIDATE", "Improving", "Breakout"): "BEARISH_RECOVERY_CANDIDATE",
}


def _fallback(structural: str, stage: str, trigger: str) -> str:
    """非矩阵组合的文档化兜底规则"""
    if structural in BULLISH_FAMILY:
        if stage == "Improving" and trigger == "Breakout":
            return "BULLISH_CONFIRMED"
        if trigger == "Breakdown":
            # P0-A：BULLISH + 任意阶段 + 周线破位 → 价格层结构性损坏 → 警告（REDUCE）
            return "BULLISH_WARNING"
        return "BULLISH_STABLE"
    if structural == "STRUCTURAL_DIVERGENCE":
        return "BULLISH_WARNING"
    if structural in BEARISH_FAMILY:
        if stage == "Improving" and trigger == "Breakout":
            return "BEARISH_RECOVERY_CANDIDATE"
        return "BEARISH_CONFIRMED"
    if structural == "STRUCTURAL_BOTTOM_CANDIDATE":
        if stage == "Improving" and trigger == "Breakout":
            return "BEARISH_RECOVERY_CANDIDATE"
        return "BULLISH_WARNING"
    return "DATA_INSUFFICIENT"


def _assert_no_overrule(structural: str, mtf_state: str):
    if structural in BULLISH_FAMILY and mtf_state == "BEARISH_CONFIRMED":
        raise ValueError(f"层级不可越权：多头结构 {structural} 禁止输出 BEARISH_CONFIRMED")
    if structural in BEARISH_FAMILY and mtf_state in BULLISH_MTF:
        raise ValueError(f"层级不可越权：空头结构 {structural} 禁止输出 {mtf_state}")


def align_mtf(structural, stage, trigger,
              tactical_override: bool = False,
              position_52w=None, max_52w_position: float = 0.15,
              min_trigger=("Breakout",)):
    """结构 + 阶段 + 触发 → MTF_State

    Returns:
        (mtf_state, method)；method: matrix / fallback / tactical_override /
        data_insufficient

    方案 B（温和）：空头季度结构下，若开启战术试多且满足
    （周线 Breakout + 52 周位置处于极低位 < max_52w_position），
    输出 BULLISH_WARNING（预警）并携带 method="tactical_override"，
    由仓位层以观察仓（5%~35%）轻仓试错。这是对"层级不可越权"的
    显式、受约束豁免（不改变结构状态本身，只增加一条战术通道）。
    """
    if structural is None or stage is None or trigger is None \
            or structural == "STATE_UNDETERMINED":
        return "DATA_INSUFFICIENT", "data_insufficient"

    allow_all = min_trigger is None or len(min_trigger) == 0
    if tactical_override and structural in BEARISH_FAMILY \
            and (allow_all or trigger in min_trigger):
        if position_52w is not None and position_52w < max_52w_position:
            return "BULLISH_WARNING", "tactical_override"

    key = (structural, stage, trigger)
    if key in ALIGNMENT_MATRIX:
        state = ALIGNMENT_MATRIX[key]
        method = "matrix"
    else:
        state = _fallback(structural, stage, trigger)
        method = "fallback"
    _assert_no_overrule(structural, state)
    return state, method


def structure_behavior_alignment(structural, stage) -> str:
    """结构-行为背离检测"""
    if structural is None or stage is None or structural == "STATE_UNDETERMINED":
        return "Unknown"
    if structural in BULLISH_FAMILY and stage == "Deteriorating":
        return "Divergence"
    if structural in BEARISH_FAMILY and stage == "Improving":
        return "Divergence"
    return "Aligned"
