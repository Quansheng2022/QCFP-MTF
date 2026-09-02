# coding: utf-8
"""Capacity / Market Impact（QCFP-MTF 2.8：把理论仓位变成可执行仓位）

    Position Size → ADV → Participation Rate → Estimated Market Impact
    → Execution Cost / Exit Liquidity / Stress Exit Days
平方根冲击模型：impact = k × sqrt(参与额 / ADV)。

2.8（35 号）：策略容量引擎——回答"这套策略到底能管理多少钱"：
    Capacity @ 1%/3%/5%/10% ADV，并按冲击/退出压力给出
    Efficient / Acceptable / Capacity Degraded 三档。
"""

import math


def market_impact(position_value, adv, participation=0.10, k=0.1) -> float:
    """估计市场冲击（比例）：k × sqrt(参与额/ADV)"""
    adv = float(adv or 0.0)
    pv = float(position_value or 0.0)
    order = pv * min(float(participation), 1.0)
    if adv <= 0 or order <= 0:
        return 0.0
    return round(k * math.sqrt(order / adv), 6)


def participation_rate(position_value, adv) -> float:
    if float(adv or 0.0) <= 0:
        return None
    return round(float(position_value) / float(adv), 6)


def exit_stress_days(position_value, adv, participation=0.10) -> int:
    """按参与率每日可成交额计算的退出所需天数"""
    adv = float(adv or 0.0)
    if adv <= 0:
        return None
    daily_cap = adv * float(participation)
    if daily_cap <= 0:
        return None
    return int(math.ceil(float(position_value) / daily_cap))


def liquidity_adjusted_risk(position_value, adv, weekly_vol,
                            participation=0.10) -> float:
    """流动性调整风险：仓位/ADV 占比 × 周波动"""
    pr = participation_rate(position_value, adv)
    if pr is None or weekly_vol is None:
        return None
    return round(pr * float(weekly_vol), 6)


def capacity_assessment(position_value, adv, weekly_vol,
                        participation=0.10,
                        max_impact=0.01, max_stress_days=3) -> dict:
    """综合评估：返回 impact / stress_days / 流动性调整风险 + 标记"""
    impact = market_impact(position_value, adv, participation)
    days = exit_stress_days(position_value, adv, participation)
    lrisk = liquidity_adjusted_risk(position_value, adv, weekly_vol,
                                    participation)
    flags = []
    if impact > max_impact:
        flags.append("HIGH_IMPACT")
    if days is not None and days > max_stress_days:
        flags.append("SLOW_EXIT")
    if lrisk is not None and lrisk > 0.05:
        flags.append("LIQUIDITY_RISK")
    return {"position_value": round(float(position_value), 2),
            "impact": impact, "stress_exit_days": days,
            "liquidity_adj_risk": lrisk, "flags": flags}


def _capacity_band(impact, exit_days) -> str:
    if impact <= 0.01 and exit_days <= 2:
        return "Efficient"
    if impact <= 0.05 and exit_days <= 5:
        return "Acceptable"
    return "Capacity Degraded"


def strategy_capacity(adv, participation_levels=(0.01, 0.03, 0.05, 0.10),
                      max_impact=0.01, max_stress_days=3,
                      turnover=1.0) -> dict:
    """策略容量：在给定 ADV 与参与率档位下，可承载的资金规模。

    容量 = ADV × participation × capacity_factor
    （capacity_factor 由换手率折算：换手越高，同规模下冲击越大。
     默认 turnover=1 即周换手 1 次；换手 2x → 容量减半。）
    """
    adv = float(adv or 0.0)
    factor = max(0.1, 1.0 / max(0.1, float(turnover or 1.0)))
    rows = []
    for pct in participation_levels:
        cap = adv * float(pct) * factor
        impact = market_impact(cap, adv, participation=1.0)
        days = exit_stress_days(cap, adv, participation=float(pct))
        rows.append({
            "participation": float(pct),
            "capacity": round(cap, 2),
            "impact": impact,
            "stress_exit_days": days,
            "band": _capacity_band(impact, days or 999),
        })
    return {"adv": round(adv, 2), "turnover": float(turnover),
            "rows": rows,
            "efficient_capacity": rows[0]["capacity"] if rows else 0.0,
            "summary": {f"{r['participation']:.0%}": r["band"]
                        for r in rows}}


def capacity_cap_target(target, capital, adv, participation=0.10,
                        max_impact=0.01, k=0.1) -> dict:
    """Target 受市场容量约束（23 号）：
        Target → 订单市值 → Execution Capacity → 可成交仓位

    约束：
        1) 单日容量 = ADV × participation；目标市值超出 → 压到容量
        2) 市场冲击 impact = k×sqrt(参与额/ADV)；超过 max_impact
           → 反解最大可成交市值 = ADV×(max_impact/k)²/participation
    """
    capital = float(capital or 0.0)
    adv = float(adv or 0.0)
    t = float(target or 0.0)
    if capital <= 0 or adv <= 0:
        return {"target": round(t, 4), "capped": False,
                "reason": "NO_CAPACITY_INPUT"}
    target_value = t * capital
    daily_cap = adv * float(participation)
    impact_cap_value = adv * (float(max_impact) / float(k)) ** 2 \
        / float(participation) if participation > 0 else 0.0
    capacity_value = min(daily_cap, impact_cap_value)
    capped_value = min(target_value, capacity_value)
    capped = capped_value < target_value - 1e-9
    return {
        "target": round(capped_value / capital, 4),
        "original_target": round(t, 4),
        "capacity_value": round(capacity_value, 2),
        "target_value": round(target_value, 2),
        "capped": capped,
        "reason": "CAPACITY_CAPPED" if capped else "WITHIN_CAPACITY",
    }


def alpha_capacity(adv, capital_levels=(100_000, 1_000_000, 5_000_000,
                                        10_000_000),
                   base_sharpe=1.8, participation=0.10,
                   decay_exponent=0.35) -> dict:
    """Alpha 容量曲线（79 号）：
        Capital → Slippage↑ → Impact↑ → Sharpe↓

    Sharpe(c) = base_sharpe × (base_capital / c)^decay_exponent
    容量衰减：规模翻倍 → Sharpe 按指数衰减。
    """
    base_cap = float(capital_levels[0]) if capital_levels else 100_000.0
    rows = []
    for c in capital_levels:
        c = float(c)
        ratio = base_cap / max(c, 1e-9)
        sharpe = float(base_sharpe) * (ratio ** float(decay_exponent))
        cap_value = min(adv * float(participation), c)
        rows.append({"capital": c,
                     "sharpe": round(sharpe, 4),
                     "capacity_value": round(cap_value, 2),
                     "capacity_ratio": round(cap_value / max(c, 1e-9), 4),
                     "decay_vs_base": round(sharpe / float(base_sharpe), 4)})
    # 最大有效规模：Sharpe 降到 0.8 以下视为容量衰减严重
    efficient = [r for r in rows if r["sharpe"] >= 0.8]
    max_efficient = efficient[-1]["capital"] if efficient else rows[0][
        "capital"]
    return {"base_sharpe": float(base_sharpe),
            "rows": rows,
            "max_efficient_capital": float(max_efficient),
            "capacity_decay": {
                "at_10x": rows[-1]["decay_vs_base"] if len(rows) > 1
                else 1.0},
            "verdict": "EFFICIENT" if rows[-1]["sharpe"] >= 1.0
            else "DEGRADED" if rows[-1]["sharpe"] >= 0.8
            else "CAPACITY_LIMITED"}
