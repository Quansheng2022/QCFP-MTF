# coding: utf-8
"""Portfolio-level Risk Aggregator（QCFP-MTF 2.8：16 号组合风险聚合器）

从"个股风险控制"升级为"组合风险控制"：
    Gross / Net / Sector / Factor / Liquidity / Correlation / Crowding /
    Drawdown Contribution / VaR / Expected Shortfall

名义暴露 → 有效暴露（A+B+C 同 AI → 1 个共同风险因子）。
"""

import numpy as np

from .exposure_engine import effective_risk_exposure, group_exposure
from .risk_contagion import conditional_loss, marginal_and_component_var, \
    portfolio_var


def portfolio_risk_aggregator(positions, corr_matrix=None,
                              returns_matrix=None, risk_budget=0.05,
                              annual_periods=52) -> dict:
    """组合风险聚合。

    positions：[{stock_code, weight, sector, theme, factor, beta, adv}]
    """
    weights = [float(p.get("weight") or 0.0) for p in positions]
    total = sum(weights)
    gross = total
    net = sum(float(p.get("weight") or 0.0)
              for p in positions)  # 港股多头
    sector = group_exposure(positions, "sector")
    theme = group_exposure(positions, "theme")
    factor = group_exposure(positions, "factor")
    eff = effective_risk_exposure(positions, corr_matrix=corr_matrix)
    # 流动性：低 ADV 持仓占比
    low_liq = sum(float(p.get("weight") or 0.0) for p in positions
                  if (p.get("adv") or 0) < 1e7)
    # VaR / ES
    var95 = None
    es = None
    if returns_matrix is not None:
        r = np.asarray(returns_matrix, float)
        port = r @ np.asarray(weights, float)
        var95 = float(np.quantile(port, 0.05))
        es = conditional_loss(r, weights, q=0.05)
    # 拥挤度：主题集中度代理
    crowding = max(theme.values()) if theme else 0.0
    return {
        "gross_exposure": round(gross, 4),
        "net_exposure": round(net, 4),
        "sector_exposure": sector,
        "theme_exposure": theme,
        "factor_exposure": factor,
        "liquidity_exposure": round(low_liq, 4),
        "correlation_risk": {
            "nominal_exposure": eff["nominal_exposure"],
            "effective_exposure": eff["effective_risk_exposure"],
            "reduction_pct": eff["reduction_pct"]},
        "crowding_risk": round(crowding, 4),
        "var95": round(var95, 6) if var95 is not None else None,
        "expected_shortfall": round(es, 6) if es is not None else None,
        "risk_budget": round(float(risk_budget), 4),
        "risk_budget_used": round(abs(var95 or 0.0) / max(
            float(risk_budget), 1e-9), 4) if var95 is not None else None,
    }
