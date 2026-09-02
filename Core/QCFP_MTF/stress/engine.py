# coding: utf-8
"""Stress Scenario Engine（QCFP-MTF 2.8：最坏情况下能否活下来）

市场冲击（-5%..-20%）/ 波动率冲击（×1.5/2/3）/
流动性冲击（成本×2/×5、ADV↓30/50%）/ 相关性冲击（0.3→0.8~1.0）
重点观察：MDD / 风险预算 / 强制退出 / 恢复天数。

2.8（26 号）：补全流动性冲击情景（ADV -30%/-50%、Spread ×2/×5）与
全量输出（Tail Loss / Risk Budget Breach / Forced Exit / Liquidity Risk）。
"""

import math

import numpy as np


def market_shock(returns, shock=-0.10, week=0) -> np.ndarray:
    """把指定周收益替换为冲击值（单周市场冲击）"""
    r = np.array(returns, dtype=float).copy()
    r[week] = shock
    return r


def vol_shock(returns, factor=2.0) -> np.ndarray:
    """波动率冲击：收益去均值后按因子缩放（保持方向）"""
    r = np.array(returns, dtype=float)
    return (r - r.mean()) * factor


def correlation_vol_scale(n=10, corr_base=0.3, corr_stress=0.9) -> float:
    """相关性冲击下的组合波动放大系数（等权近似）"""
    def _factor(c):
        return (1 + (n - 1) * c) / n
    return math.sqrt(_factor(corr_stress) / max(1e-9, _factor(corr_base)))


def mdd(returns) -> float:
    equity = np.cumprod(1 + np.array(returns, dtype=float))
    peak = np.maximum.accumulate(equity)
    return float((equity / peak - 1).min())


def recovery_days(returns) -> int:
    """从最大回撤恢复到前高所需周数（-1 = 未恢复）"""
    equity = np.cumprod(1 + np.array(returns, dtype=float))
    peak = np.maximum.accumulate(equity)
    trough = int(np.argmin(equity / peak - 1))
    pre = peak[trough]
    for i in range(trough + 1, len(equity)):
        if equity[i] >= pre:
            return i - trough
    return -1


def stress_scenarios(returns, n=10, cost_scale=2.0) -> list:
    """标准压力矩阵 → 每情景 {name, mdd, recovery_days}"""
    r = np.array(returns, dtype=float)
    rows = [{"name": "baseline", "mdd": mdd(r),
             "recovery_days": recovery_days(r), "cost_scale": 1.0}]
    for shock in (-0.05, -0.10, -0.15, -0.20):
        s = market_shock(r, shock=shock)
        rows.append({"name": f"market_{abs(shock):.0%}", "mdd": mdd(s),
                     "recovery_days": recovery_days(s), "cost_scale": 1.0})
    for f in (1.5, 2.0, 3.0):
        s = vol_shock(r, factor=f)
        rows.append({"name": f"vol_x{f}", "mdd": mdd(s),
                     "recovery_days": recovery_days(s), "cost_scale": 1.0})
    rows.append({"name": "correlation_0.9",
                 "mdd": mdd(r * correlation_vol_scale(n=n, corr_stress=0.9)),
                 "recovery_days": recovery_days(
                     r * correlation_vol_scale(n=n, corr_stress=0.9)),
                 "cost_scale": cost_scale})
    return rows


def liquidity_stress_scenarios(returns, adv_scale=0.7, spread_scale=2.0) -> list:
    """流动性冲击情景：成交额缩减 + 价差扩大 → 对净收益的额外损耗。"""
    rows = []
    for adv in (0.7, 0.5):
        for spread in (2.0, 5.0):
            # 冲击成本近似：净收益 = 毛收益 - 成本；成本随价差/流动性恶化放大
            cost_mult = spread / adv
            net = np.array(returns, dtype=float) - (cost_mult - 1.0) * 0.002
            rows.append({
                "name": f"liq_adv{adv:.0%}_spread{spread:.0f}x",
                "mdd": mdd(net),
                "recovery_days": recovery_days(net),
                "cost_scale": round(cost_mult, 3),
                "adv_scale": adv,
                "spread_scale": spread,
            })
    return rows


def tail_loss(returns, q=0.05) -> float:
    """Tail Loss（VaR）：收益分布 q 分位数（负值表示损失）。"""
    r = np.array(returns, dtype=float)
    if len(r) == 0:
        return 0.0
    return round(float(np.quantile(r, q)), 4)


def risk_budget_breach(returns, budget=0.10) -> dict:
    """风险预算突破：单周最大回撤或累计回撤超过预算 → breach。"""
    r = np.array(returns, dtype=float)
    eq = np.cumprod(1 + r)
    peak = np.maximum.accumulate(eq)
    dd = float((eq / peak - 1).min())
    worst_week = float(r.min()) if len(r) else 0.0
    return {
        "max_drawdown": round(dd, 4),
        "worst_week": round(worst_week, 4),
        "budget": float(budget),
        "breach": bool(abs(dd) > budget or worst_week < -budget),
    }


def full_stress_report(returns, n=10, risk_budget=0.10,
                       vol_levels=(1.5, 2.0, 3.0),
                       liquidity_adv_scales=(0.7, 0.5),
                       liquidity_spread_scales=(2.0, 5.0)) -> dict:
    """完整压力报告：市场/波动/相关性/流动性 + Tail Loss/风险预算/强制退出。

    输出字段：
        scenarios        各情景 {name, mdd, recovery_days, cost_scale, ...}
        tail_loss        VaR95
        risk_budget      {max_drawdown, worst_week, breach}
        forced_exit      最大回撤超 -20% 的情景数（生存能力）
        liquidity_risk   LIQUIDITY_LOW 情景数（流动性恶化下退出困难）
    """
    r = np.array(returns, dtype=float)
    scenarios = stress_scenarios(r, n=n)
    scenarios += liquidity_stress_scenarios(r)
    forced_exit = sum(
        1 for s in scenarios if s.get("mdd", 0.0) <= -0.20)
    liquidity_risk = sum(
        1 for s in scenarios if "liq_" in s.get("name", "")
        and s.get("cost_scale", 1.0) >= 4.0)
    return {
        "scenarios": scenarios,
        "tail_loss": tail_loss(r),
        "risk_budget": risk_budget_breach(r, budget=risk_budget),
        "forced_exit_count": forced_exit,
        "liquidity_risk_count": liquidity_risk,
        "survivable": forced_exit < len(scenarios),
    }
