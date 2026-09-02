# coding: utf-8
"""Cross-Section Opportunity Ranking（QCFP-MTF 2.8）

20 个机会同时出现时，有限资金优先配置哪几个。
Ranking 不改变 Permission：BLOCK + Rank#1 仍然不可交易。

2.8（22 号）：补全排序维度——预期持有期（越短资金周转越快）与
资本效率（单位风险/单位暴露下的预期收益），九维排序。
"""


def opportunity_score(row, settings=None, liquidity_score=1.0) -> float:
    """复合机会分（0-100）：九维——
    机构对齐/波强/进场质量/风险收益/流动性/MFE/MAE/权限稳定/持有期/资本效率"""
    perm = {"BLOCK": 0, "WATCH": 3, "TEST": 8, "ALLOW": 12,
            "STRONG_ALLOW": 15}.get(row.get("institutional_permission"), 0)
    setup = {"BREAKOUT": 20, "PULLBACK": 17, "RECOVERY": 14,
             "ACCUMULATION": 10, "NONE": 0}.get(row.get("setup_type"), 0)
    tqs = float(row.get("trade_quality") or 0.0) * 0.25
    risk = {"Low": 15, "Medium": 10, "High": 3,
            "Extreme": 0}.get(row.get("risk_level"), 6)
    liq = min(5.0, float(liquidity_score))
    wave = min(10.0, float(row.get("wave_strength") or 0.0) * 10)
    mfe = min(5.0, float(row.get("mfe_potential") or 0.0) * 25)
    mae_risk = 5.0 - min(5.0, abs(float(row.get("mae_risk") or 0.0)) * 25)
    perm_stable = 5.0 if row.get("permission_stable") else 2.0
    # 持有期：预期持有越短，资金周转越快（≤4 周满分，>12 周 0）
    holding = float(row.get("expected_holding_weeks") or 4.0)
    holding_score = max(0.0, min(5.0, 5.0 - (holding - 4.0) / 2.0))
    # 资本效率：预期年化/暴露（或 MFE 与 MAE 赔率归一化）
    cap_eff_raw = float(row.get("capital_efficiency") or 0.0)
    if cap_eff_raw <= 0 and row.get("expected_mfe") is not None \
            and row.get("expected_mae"):
        mae = max(0.0001, abs(float(row.get("expected_mae"))))
        cap_eff_raw = float(row.get("expected_mfe") or 0.0) / mae
    cap_eff = min(5.0, max(0.0, cap_eff_raw * 1.0))
    return round(min(100.0, perm + setup + tqs + risk + liq + wave
                     + mfe + mae_risk + perm_stable
                     + holding_score + cap_eff), 2)


def rank_opportunities(rows, settings=None, liquidity_map=None) -> list:
    """横截面排序（降序）；BLOCK 强制 tradable=False（Rank 不越权）"""
    out = []
    for r in rows:
        liq = 1.0
        if liquidity_map:
            liq = liquidity_map.get(r.get("stock_code"), 1.0)
        score = opportunity_score(r, settings, liquidity_score=liq)
        out.append({
            "stock_code": r.get("stock_code"),
            "score": score,
            "permission": r.get("institutional_permission"),
            "setup": r.get("setup_type"),
            "tradable": r.get("institutional_permission") != "BLOCK",
        })
    return sorted(out, key=lambda x: x["score"], reverse=True)


def select_top_n(ranked, n=3):
    """Top-N 候选（仅 tradable）"""
    return [x for x in ranked if x["tradable"]][:n]


def risk_adjusted_opportunity_score(row, probability=1.0,
                                    liquidity_score=1.0,
                                    execution_cost=None) -> float:
    """风险调整机会评分（52 号）：
        Risk-adjusted Opportunity = Expected Edge / Expected Risk

    Expected Edge = Expected MFE × Probability × Remaining Ratio × Entry 质量
    Expected Risk = MAE（+ 持有期成本 + 流动性成本）
    输出单位风险下的机会价值（越高越值得占用资金）。
    """
    mfe = max(0.0, float(row.get("expected_mfe")
                         or row.get("mfe_potential") or 0.0))
    mae = max(0.0001, abs(float(row.get("expected_mae")
                                or row.get("mae_risk") or 0.0)))
    remaining = max(0.0, 1.0 - float(row.get("realized_mfe_ratio") or 0.0))
    entry_scale = {"OPTIMAL": 1.0, "ACCEPTABLE": 0.8, "EARLY": 0.7,
                   "LATE": 0.4, "INVALID": 0.0}.get(
        row.get("entry_timing") or row.get("timing_band"), 0.7)
    holding_cost = max(0.0, (float(row.get("expected_holding_weeks") or 4)
                             - 4.0) * 0.01)
    cost = float(execution_cost if execution_cost is not None
                 else row.get("execution_cost") or 0.005)
    liq_cost = (1.0 - float(liquidity_score or 1.0)) * 0.01
    edge = mfe * float(probability) * remaining * entry_scale
    risk = mae + holding_cost + cost + liq_cost
    score = edge / risk if risk > 0 else 0.0
    return round(score, 4)
