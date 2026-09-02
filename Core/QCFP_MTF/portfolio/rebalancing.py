# coding: utf-8
"""Portfolio Rebalancing Governance（QCFP-MTF 2.8：66 号组合再平衡治理）

防止排名每天微变导致过度调仓：
    Rebalance Band / Minimum Trade Size / Minimum Expected Benefit /
    Cooldown Period / Transaction Cost Threshold

例：Target=5% 但 Current=4.8%，未达 Minimum Rebalance Threshold → NO TRADE。
"""

from datetime import datetime


def rebalance_decision(target, current, rebalance_band=0.01,
                       min_trade_size=0.01, min_expected_benefit=0.005,
                       cooldown_days=5, last_trade_date=None,
                       today=None, transaction_cost=0.001) -> dict:
    """再平衡判定。

    规则：
        1) |target − current| < band → NO_TRADE（微小偏差不调）
        2) 调整量 < min_trade_size → NO_TRADE（低于最小交易规模）
        3) 冷却期内 → NO_TRADE
        4) 预期收益 < 交易成本 + min_expected_benefit → NO_TRADE
    """
    target = float(target or 0.0)
    current = float(current or 0.0)
    delta = target - current
    reasons = []
    if abs(delta) < float(rebalance_band):
        return {"trade": False, "reason": "WITHIN_BAND",
                "delta": round(delta, 4)}
    if abs(delta) < float(min_trade_size):
        return {"trade": False, "reason": "BELOW_MIN_TRADE_SIZE",
                "delta": round(delta, 4)}
    if last_trade_date:
        t = today or datetime.now().strftime("%Y-%m-%d")
        try:
            d1 = datetime.strptime(str(last_trade_date)[:10], "%Y-%m-%d")
            d2 = datetime.strptime(str(t)[:10], "%Y-%m-%d")
            if (d2 - d1).days < int(cooldown_days):
                return {"trade": False, "reason": "COOLDOWN",
                        "delta": round(delta, 4)}
        except ValueError:
            pass
    # 预期收益 = 调整量（近似目标价差收益），须覆盖成本+最低收益
    benefit = abs(delta)
    cost = float(transaction_cost or 0.0) + float(min_expected_benefit or 0.0)
    if benefit <= cost:
        return {"trade": False, "reason": "BENEFIT_BELOW_COST",
                "delta": round(delta, 4),
                "benefit": round(benefit, 4), "cost": round(cost, 4)}
    return {"trade": True, "reason": "REBALANCE_OK",
            "delta": round(delta, 4),
            "action": "ADD" if delta > 0 else "REDUCE"}
