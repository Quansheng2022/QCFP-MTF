# coding: utf-8
"""Risk Contagion Engine（QCFP-MTF 2.8：34 号风险传染/联动引擎）

一个仓位出问题会不会拖累其他仓位：
    Market Shock → Stock A → Sector Risk → Stock B/C/D → Portfolio DD

计算：
    Marginal VaR / Component VaR / Conditional Loss(CVaR) /
    Cluster Stress / Liquidity Contagion

并接入 Governance：
    Portfolio Risk → Risk Contagion → Available Risk Budget → Position Cap
"""

import numpy as np


def portfolio_var(weights, cov, z=1.645) -> float:
    """组合 VaR = z × sqrt(w'Σw)。"""
    w = np.asarray(weights, float)
    c = np.asarray(cov, float)
    v = float(np.sqrt(max(0.0, w @ c @ w)))
    return round(z * v, 6)


def marginal_and_component_var(weights, cov, z=1.645) -> dict:
    """Marginal VaR / Component VaR（成分 = 权重 × 边际）。"""
    w = np.asarray(weights, float)
    c = np.asarray(cov, float)
    sigma = float(np.sqrt(max(0.0, w @ c @ w)))
    if sigma == 0:
        return {"marginal_var": {}, "component_var": {},
                "total_component_var": 0.0}
    marginal = z * (c @ w) / sigma
    component = w * marginal
    return {
        "marginal_var": {i: round(float(v), 6) for i, v in enumerate(marginal)},
        "component_var": {i: round(float(v), 6)
                          for i, v in enumerate(component)},
        "total_component_var": round(float(component.sum()), 6),
    }


def conditional_loss(returns_matrix, weights, q=0.05) -> float:
    """CVaR / Conditional Loss：组合收益 q 分位以下的平均损失。"""
    r = np.asarray(returns_matrix, float)
    w = np.asarray(weights, float)
    if r.shape[0] == 0 or r.shape[1] != len(w):
        return 0.0
    port = r @ w
    thr = float(np.quantile(port, q))
    tail = port[port <= thr]
    if len(tail) == 0:
        return 0.0
    return round(float(-tail.mean()), 6)


def cluster_stress(clusters, cluster_returns, weights_by_stock,
                   shock=-0.10) -> dict:
    """簇压力：对每个相关性簇施加冲击，计算组合损失贡献。"""
    out = {}
    total_w = sum(float(weights_by_stock.get(s, 0.0))
                  for c in clusters for s in c)
    for i, c in enumerate(clusters):
        cw = sum(float(weights_by_stock.get(s, 0.0)) for s in c)
        c_ret = float(cluster_returns.get(i, shock)) if \
            isinstance(cluster_returns, dict) else float(shock)
        out[f"cluster_{i}"] = {
            "stocks": c,
            "weight": round(cw, 4),
            "shock_return": round(c_ret, 4),
            "loss_contribution": round(-cw * c_ret, 6),
            "loss_share": round(cw * abs(c_ret) / max(1e-9, total_w),
                                4) if total_w else 0.0,
        }
    return out


def liquidity_contagion(positions, adv_map, illiquid_threshold_days=3,
                        corr_matrix=None, corr_threshold=0.7) -> dict:
    """流动性传染：某仓退出困难（天数超阈）+ 与其它仓高相关 → 联动风险。"""
    illiquid = [p.get("stock_code") for p in positions
                if float(adv_map.get(p.get("stock_code"), 0.0) or 0.0) <= 0
                or (p.get("exit_days") or 0) > illiquid_threshold_days]
    contagion = []
    if illiquid and corr_matrix:
        for s in illiquid:
            linked = [k for k in corr_matrix.get(s, {})
                      if k != s
                      and float(corr_matrix[s].get(k, 0.0)) >= corr_threshold]
            if linked:
                contagion.append({"source": s, "linked": linked})
    return {
        "illiquid_positions": sorted(illiquid),
        "contagion_links": contagion,
        "liquidity_contagion_risk": bool(contagion),
    }


def contagion_cap_scale(component_var, risk_budget, max_scale=0.5) -> float:
    """风险传染 → 可用风险预算 → 仓位上限缩放：
    最大成分 VaR 占风险预算比例越高，可新增仓位越小。
    """
    if not component_var or float(risk_budget or 0.0) <= 0:
        return 1.0
    max_comp = max(abs(v) for v in component_var.values())
    ratio = max_comp / float(risk_budget)
    scale = max(0.0, min(max_scale, 1.0 - ratio))
    return round(scale, 4)


def risk_contagion_report(weights, cov, returns_matrix=None, clusters=None,
                          cluster_returns=None, positions=None, adv_map=None,
                          corr_matrix=None, risk_budget=0.05) -> dict:
    """完整风险传染报告。"""
    w = np.asarray(weights, float)
    var95 = portfolio_var(w, cov)
    mc = marginal_and_component_var(w, cov)
    cv = conditional_loss(returns_matrix, w) if returns_matrix is not None \
        else None
    cl = cluster_stress(clusters or [], cluster_returns or {}, {
        p.get("stock_code"): p.get("weight") for p in (positions or [])}
        if positions else {}) if clusters else {}
    lq = liquidity_contagion(positions or [], adv_map or {}, corr_matrix=corr_matrix) \
        if positions else {"illiquid_positions": [], "contagion_links": [],
                           "liquidity_contagion_risk": False}
    scale = contagion_cap_scale(mc["component_var"], risk_budget)
    return {
        "portfolio_var95": var95,
        "marginal_component_var": mc,
        "conditional_loss_cvar": cv,
        "cluster_stress": cl,
        "liquidity_contagion": lq,
        "available_risk_budget": round(float(risk_budget), 4),
        "position_cap_scale": scale,
    }
