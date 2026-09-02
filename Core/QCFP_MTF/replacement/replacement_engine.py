# coding: utf-8
"""Opportunity Replacement Engine（QCFP-MTF 2.8）

新机会出现时，是否值得卖掉旧机会换仓：
    Replacement Utility = New Opportunity Utility
    > Existing Position Utility + Switching Cost
    才允许换仓。

2.8（23 号）：换仓判定补充"当前 Wave 阶段 / 剩余资金效率 / 换仓风险"——
    旧仓处于 MATURE/EXHAUSTING 阶段或剩余效率低时，换仓门槛降低；
    新仓处于 DISCOVERY/CONFIRMING 且质量不足时，门槛提高。
"""


def position_utility(row, settings=None, liquidity_score=1.0) -> float:
    """既有/候选机会的效用（复用 Cross-Section 机会分）"""
    from ..ranking.opportunity_ranking import opportunity_score
    return opportunity_score(row, settings, liquidity_score=liquidity_score)


def switching_cost(commission_rate=0.0025, slippage_rate=0.001,
                   position=0.3) -> float:
    """换仓成本 ≈ 双边费率 + 滑点，按仓位比例折算为效用扣减"""
    return (float(commission_rate) * 2 + float(slippage_rate)) \
        * max(0.0, float(position))


def _stage_adjust(stage: str, is_existing: bool) -> float:
    """生命周期阶段对效用的调整（0.9~1.1）：
    - 旧仓 MATURE/EXHAUSTING → 效用 ×0.92（机会衰减，倾向换）
    - 旧仓 ACTIVE → ×1.05（趋势存活，倾向留）
    - 新仓 DISCOVERY/CONFIRMING → ×0.95（未确认，保守）
    - 新仓 ACTIVE/CONFIRMING+ → ×1.0
    """
    s = str(stage or "").upper()
    if is_existing:
        if s in ("MATURE", "EXHAUSTING", "INVALID"):
            return 0.92
        if s == "ACTIVE":
            return 1.05
        return 1.0
    if s in ("DISCOVERY", "CONFIRMING"):
        return 0.95
    return 1.0


def should_replace(candidate_row, existing_row, settings=None,
                   position=0.3, min_edge=0.0,
                   liquidity_map=None) -> dict:
    """判定是否换仓：仅当新机会效用 > 旧仓效用 + 换仓成本"""
    cu = position_utility(candidate_row, settings,
                          liquidity_map.get(candidate_row.get("stock_code"), 1.0)
                          if liquidity_map else 1.0)
    eu = position_utility(existing_row, settings,
                          liquidity_map.get(existing_row.get("stock_code"), 1.0)
                          if liquidity_map else 1.0)
    cu *= _stage_adjust(candidate_row.get("wave_stage"), is_existing=False)
    eu *= _stage_adjust(existing_row.get("wave_stage"), is_existing=True)
    cost = switching_cost(position=position)
    edge = cu - eu - cost
    return {"candidate_utility": round(cu, 2),
            "existing_utility": round(eu, 2),
            "switching_cost": round(cost, 4),
            "edge": round(edge, 2),
            "replace": edge > min_edge,
            "candidate_stage": candidate_row.get("wave_stage") or "",
            "existing_stage": existing_row.get("wave_stage") or "",
            "stage_adjust": {
                "candidate": _stage_adjust(candidate_row.get("wave_stage"),
                                           False),
                "existing": _stage_adjust(existing_row.get("wave_stage"),
                                          True),
            }}


def capital_rotation(existing_remaining_return, existing_holding_days,
                     candidate_expected_return, candidate_holding_days,
                     transaction_cost=0.01, risk_penalty=0.005,
                     min_edge=0.0) -> dict:
    """资本周转优化（65 号）：
        优化资本周转而非交易次数。

    B 增量边际收益 = B 日化收益 × A 剩余天数 − A 剩余收益
    若 > 交易成本 + 风险罚金 → 换仓。
    """
    a_ret = float(existing_remaining_return or 0.0)
    a_days = max(1, int(existing_holding_days or 1))
    b_ret = float(candidate_expected_return or 0.0)
    b_days = max(1, int(candidate_holding_days or 1))
    # 把 B 的预期收益折算到 A 的剩余持有期内
    b_daily = b_ret / b_days
    b_projected = b_daily * a_days
    incremental = b_projected - a_ret
    cost = float(transaction_cost or 0.0) + float(risk_penalty or 0.0)
    edge = incremental - cost
    return {
        "existing_remaining_return": round(a_ret, 4),
        "candidate_projected_return": round(b_projected, 4),
        "incremental_edge": round(incremental, 4),
        "total_cost": round(cost, 4),
        "net_edge": round(edge, 4),
        "rotate": bool(edge > float(min_edge)),
    }
