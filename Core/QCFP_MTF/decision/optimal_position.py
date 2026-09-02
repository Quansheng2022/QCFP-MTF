# coding: utf-8
"""Position Sizing Engine 2.0（QCFP-MTF 2.8：25 号最优风险仓位）

最大允许仓位 ≠ 最优仓位：
    Maximum Allowed → Risk-optimal → Liquidity-optimal → Executable

Position Size = f(Expected Edge, Risk, Confidence, Portfolio, Liquidity)
"""


def optimal_position(edge, risk, confidence, max_allowed,
                     liquidity_scale=1.0, portfolio_scale=1.0,
                     win_probability=None) -> dict:
    """最优仓位。

    edge：预期边际收益（0-1）；risk：预期风险（0-1）；
    confidence：置信度（0-1）；max_allowed：治理允许上限。
    """
    max_allowed = float(max_allowed or 0.0)
    edge = float(edge or 0.0)
    risk = max(0.001, float(risk or 0.0))
    confidence = float(confidence or 0.0)
    liq = float(liquidity_scale or 1.0)
    port = float(portfolio_scale or 1.0)
    # 风险最优：Kelly 风格（edge/risk × 置信度折扣，cap 50%）
    risk_optimal = min(0.5, (edge / risk) * confidence * 0.5)
    risk_optimal = min(risk_optimal, max_allowed)
    # 流动性/组合最优
    liq_optimal = risk_optimal * min(liq, port)
    executable = min(liq_optimal, max_allowed)
    return {
        "maximum_allowed": round(max_allowed, 4),
        "risk_optimal": round(risk_optimal, 4),
        "liquidity_optimal": round(liq_optimal, 4),
        "executable_position": round(executable, 4),
        "win_probability": round(float(win_probability or 0.0), 4),
        "binding": "MAX_ALLOWED" if executable >= max_allowed - 1e-9
        else "LIQUIDITY" if executable < liq_optimal - 1e-9
        else "RISK_OPTIMAL",
    }


def position_from_components(edge, risk, confidence, max_allowed,
                             win_probability=None) -> dict:
    """简化入口：edge/risk/confidence → 最优仓位。"""
    return optimal_position(edge, risk, confidence, max_allowed,
                            win_probability=win_probability)
