# coding: utf-8
"""Trade Outcome Attribution（QCFP-MTF 2.8：26 号交易结果归因）

一次交易盈利/亏损究竟来自哪里：
    Raw opportunity / Entry delay / Early exit / Slippage /
    Position cap / Permission constraint → Realized contribution

回答："系统选股错了，还是买点错了，还是卖点错了，还是执行约束吃掉收益？"
"""


def trade_outcome_attribution(trade: dict) -> dict:
    """trade：{raw_opportunity, entry_delay_cost, early_exit_cost,
    slippage_cost, position_cap_cost, permission_cost, realized_return}"""
    raw = float(trade.get("raw_opportunity") or 0.0)
    parts = {
        "entry_delay": -abs(float(trade.get("entry_delay_cost") or 0.0)),
        "early_exit": -abs(float(trade.get("early_exit_cost") or 0.0)),
        "slippage": -abs(float(trade.get("slippage_cost") or 0.0)),
        "position_cap": -abs(float(trade.get("position_cap_cost") or 0.0)),
        "permission_constraint": -abs(
            float(trade.get("permission_cost") or 0.0)),
    }
    realized = raw + sum(parts.values())
    return {
        "raw_opportunity": round(raw, 4),
        "entry_delay": round(parts["entry_delay"], 4),
        "early_exit": round(parts["early_exit"], 4),
        "slippage": round(parts["slippage"], 4),
        "position_cap": round(parts["position_cap"], 4),
        "permission_constraint": round(parts["permission_constraint"], 4),
        "realized_contribution": round(realized, 4),
        "biggest_leak": min(parts, key=parts.get) if parts else None,
        "opportunity_quality_kept": round(realized / max(raw, 1e-9), 4),
    }
