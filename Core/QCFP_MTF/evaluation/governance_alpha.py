# coding: utf-8
"""Governance Alpha / Loss Avoidance Alpha（QCFP-MTF 2.8：P1-8）

验证"治理模块到底创造了多少价值"：
    Governance Alpha = Governed − Unrestricted

拆分：
    Loss Avoidance / Drawdown Reduction / Turnover Reduction /
    Capital Efficiency / Opportunity Cost

特别关注 Avoided Loss：BLOCK 的交易中，若交易会亏损 → 系统"不交易"的价值。
"""


def governance_alpha(governed_metrics, unrestricted_metrics) -> dict:
    """受治理 vs 不受限策略的 Alpha 对比。"""
    g = governed_metrics
    u = unrestricted_metrics
    return {
        "governed_return": round(float(g.get("return") or 0.0), 4),
        "unrestricted_return": round(float(u.get("return") or 0.0), 4),
        "governance_alpha": round(
            float(g.get("return") or 0.0) - float(u.get("return") or 0.0), 4),
        "drawdown_reduction": round(
            float(g.get("mdd") or 0.0) - float(u.get("mdd") or 0.0), 4),
        "turnover_reduction": round(
            float(u.get("turnover") or 0.0) - float(g.get("turnover") or 0.0),
            4),
        "capital_efficiency_delta": round(
            float(g.get("capital_efficiency") or 0.0)
            - float(u.get("capital_efficiency") or 0.0), 4),
        "opportunity_cost": round(
            max(0.0, float(u.get("return") or 0.0)
                - float(g.get("return") or 0.0)), 4),
    }


def avoided_loss(blocked_trades) -> dict:
    """Avoided Loss：被 BLOCK 的交易中，若交易会亏损则避免的损失。"""
    losses = [float(t.get("net_return") or 0.0) for t in blocked_trades
              if float(t.get("net_return") or 0.0) < 0]
    wins = [float(t.get("net_return") or 0.0) for t in blocked_trades
            if float(t.get("net_return") or 0.0) > 0]
    return {
        "blocked_count": len(blocked_trades),
        "would_lose": len(losses),
        "would_win": len(wins),
        "avoided_loss": round(-sum(losses), 4),
        "foregone_gain": round(sum(wins), 4),
        "net_avoided": round(-sum(losses) - sum(wins), 4),
    }
