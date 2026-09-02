# coding: utf-8
"""Execution Simulator（QCFP-MTF 2.8：成交假设显式化 + 全流水线仿真）

成交假设必须显式，否则无法判断策略是否依赖"理论上可成交、现实不可成交"：
    BASE     正常成交（费率×1，滑点×1，全额成交）
    STRESS   更高滑点 + 较低成交能力（滑点×3，80% 成交）
    EXTREME  流动性恶化（滑点×6，50% 成交）

成交价格口径（回测假设）：
    T 决策 → T+1 周收盘确认成交（不按周内止损价成交，无未来信息）。

2.8（27 号）：新增全流水线仿真——
    Decision → Order Intent → Order Size → Execution Model →
    Partial Fill → Slippage → Actual Position
    覆盖：T+1 / Bid-Ask Spread / 滑点 / 部分成交 / 分批成交 /
    流动性不足 / 涨跌停无法成交 / 停牌 / 市场冲击 / Exit 延迟；
    并区分 Signal Return / Gross Return / Execution Return / Net Return。
"""

import copy

SCENARIOS = {
    "C0_LOW": {"commission": 0.5, "stamp": 0.5, "slippage": 0.5,
               "fill_rate": 1.0, "participation_rate": 0.10},
    "BASE": {"commission": 1.0, "stamp": 1.0, "slippage": 1.0,
             "fill_rate": 1.0, "participation_rate": 0.10},
    "STRESS": {"commission": 1.5, "stamp": 1.0, "slippage": 3.0,
               "fill_rate": 0.80, "participation_rate": 0.05},
    "EXTREME": {"commission": 2.0, "stamp": 1.5, "slippage": 6.0,
                "fill_rate": 0.50, "participation_rate": 0.02},
}

SCENARIO_ALIASES = {"c0": "C0_LOW", "c1": "BASE", "c2": "STRESS",
                    "c3": "EXTREME"}


def apply_scenario(settings, scenario="BASE"):
    """按情景缩放佣金/印花/滑点（返回新 settings，不改原对象）"""
    sc = SCENARIOS.get(scenario, SCENARIOS["BASE"])
    s = copy.deepcopy(settings)
    cost = s.setdefault("backtest", {}).setdefault("cost", {})
    for k, mult in (("commission_rate", sc["commission"]),
                    ("stamp_rate", sc["stamp"]),
                    ("slippage_rate", sc["slippage"])):
        cost[k] = round(float(cost.get(k, 0.0)) * mult, 6)
    s.setdefault("execution", {})["scenario"] = scenario
    s["execution"]["fill_rate"] = sc["fill_rate"]
    s["execution"]["participation_rate"] = sc["participation_rate"]
    return s


def max_order_size(adv_amount, participation_rate=0.10) -> float:
    """最大可成交订单额 = 日成交额 × 参与率（流动性约束）"""
    return float(adv_amount or 0.0) * float(participation_rate)


def fill_ratio(order_amount, adv_amount, participation_rate=0.10,
               fill_rate=1.0) -> float:
    """实际成交比例 = min(1, 流动性容量/订单额) × 情景成交率"""
    cap = max_order_size(adv_amount, participation_rate)
    if order_amount <= 0:
        return 1.0
    liq = min(1.0, cap / float(order_amount)) if cap > 0 else 0.0
    return round(max(0.0, min(1.0, liq * float(fill_rate))), 4)


def simulate_execution(order_amount, adv_amount, participation_rate=0.10,
                       fill_rate=1.0, spread_bps=10.0, slippage_bps=5.0,
                       suspended=False, limit_up=False, limit_down=False,
                       batch_size=4, exit_delay_days=0,
                       market_impact_k=0.1, gap_bps=0.0,
                       fill_price_basis="close") -> dict:
    """全流水线成交仿真。

    输入：
        order_amount      目标订单额
        adv_amount        日均成交额
        participation_rate 参与率上限
        fill_rate         情景成交率（BASE=1.0/STRESS=0.8/EXTREME=0.5）
        spread_bps        买卖价差（bp）
        slippage_bps      滑点（bp）
        suspended         停牌 → 无法成交
        limit_up          涨停 → 买入无法成交
        limit_down        跌停 → 卖出无法成交
        batch_size        分批成交批数上限
        exit_delay_days   退出延迟（天）
        market_impact_k   市场冲击系数
        gap_bps           跳空成本（bp）：开盘成交与决策收盘的价差
        fill_price_basis  成交价格基准：open / close

    输出：
        filled_amount / fill_pct / batches / avg_extra_cost_bps /
        executable（是否可成交）/ reasons
    """
    import math
    from .capacity import market_impact
    reasons = []
    if float(order_amount or 0.0) <= 0:
        return {"filled_amount": 0.0, "fill_pct": 0.0, "batches": [],
                "avg_extra_cost_bps": 0.0, "executable": True,
                "reasons": ["ZERO_ORDER"]}
    if suspended:
        return {"filled_amount": 0.0, "fill_pct": 0.0, "batches": [],
                "avg_extra_cost_bps": 0.0, "executable": False,
                "reasons": ["SUSPENDED"]}
    if limit_up or limit_down:
        return {"filled_amount": 0.0, "fill_pct": 0.0, "batches": [],
                "avg_extra_cost_bps": 0.0, "executable": False,
                "reasons": ["LIMIT_BLOCKED"]}
    cap = max_order_size(adv_amount, participation_rate)
    liq_pct = min(1.0, cap / float(order_amount)) if cap > 0 else 0.0
    pct = round(max(0.0, min(1.0, liq_pct * float(fill_rate))), 4)
    if pct < 0.99:
        reasons.append("PARTIAL_FILL" if pct > 0 else "NO_LIQUIDITY")
    impact_bps = float(market_impact(
        float(order_amount), adv_amount, participation_rate,
        k=market_impact_k)) * 10000.0
    extra_cost = (float(spread_bps) + float(slippage_bps) + impact_bps
                  + float(gap_bps))
    n_batches = min(batch_size, max(1, int(math.ceil(1.0 / max(pct, 1e-6)))))
    per_batch = round(float(order_amount) * pct / n_batches, 2)
    batches = [round(per_batch, 2)] * n_batches
    return {
        "filled_amount": round(float(order_amount) * pct, 2),
        "fill_pct": pct,
        "batches": batches,
        "avg_extra_cost_bps": round(extra_cost, 2),
        "exit_delay_days": int(exit_delay_days),
        "gap_bps": round(float(gap_bps), 2),
        "fill_price_basis": str(fill_price_basis),
        "executable": pct > 0,
        "reasons": reasons or ["FULL_FILL"],
    }


def return_decomposition(signal_return, gross_return=None,
                         execution_return=None, net_return=None) -> dict:
    """收益分解：
        Signal Return    信号理论收益（按信号日收盘）
        Gross Return     不含成本的组合收益（T+1 成交口径）
        Execution Return 成交/滑点/冲击后的收益
        Net Return       扣除全部成本后的净收益
    """
    g = float(gross_return if gross_return is not None
              else signal_return or 0.0)
    e = float(execution_return if execution_return is not None else g)
    n = float(net_return if net_return is not None else e)
    return {
        "signal_return": round(float(signal_return or 0.0), 4),
        "gross_return": round(g, 4),
        "execution_return": round(e, 4),
        "net_return": round(n, 4),
        "execution_cost_impact": round(g - e, 4),
        "total_friction": round(g - n, 4),
    }


def executable_target(target, capital, adv, participation_rate=0.10,
                      slippage_bps=10.0, max_impact=0.01,
                      fill_rate=1.0) -> dict:
    """Executable Target（17 号）：
        Decision Target → Executable Target

    约束：单日容量 + 市场冲击 + 成交率 → 理论目标 10% 可能只能执行 6.5%。
    """
    from .capacity import capacity_cap_target
    cap = capacity_cap_target(
        target, capital, adv, participation=participation_rate,
        max_impact=max_impact)
    fill = fill_ratio(cap["target"] * float(capital or 0.0), adv,
                      participation_rate, fill_rate)
    executable = cap["target"] * fill
    return {
        "decision_target": round(float(target or 0.0), 4),
        "capacity_capped_target": cap["target"],
        "fill_ratio": fill,
        "executable_target": round(executable, 4),
        "reduced": executable < float(target or 0.0) - 1e-9,
        "reason": "CAPACITY_AND_FILL" if executable < float(target or 0.0)
        else "FULL_EXECUTABLE",
    }
