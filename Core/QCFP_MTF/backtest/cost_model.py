# coding: utf-8
"""港股交易成本模型（买卖不对称，可配置）

- 买入单边：佣金 + 滑点
- 卖出单边：佣金 + 印花税 + 滑点 + 交易征费/交易费
- 可选最低佣金（按单笔换手金额比例计，简化按费率档位处理）
"""


def _cost(settings):
    cfg = settings.get("backtest", {}).get("cost", {})
    return {
        "commission": float(cfg.get("commission_rate", 0.0025)),
        "stamp": float(cfg.get("stamp_rate", 0.001)),
        "slippage": float(cfg.get("slippage_rate", 0.001)),
        "levy": float(cfg.get("levy_rate", 0.00027)),
        "min_commission": float(cfg.get("min_commission", 0.0)),
    }


def buy_rate(settings) -> float:
    c = _cost(settings)
    return c["commission"] + c["slippage"]


def sell_rate(settings) -> float:
    c = _cost(settings)
    return c["commission"] + c["stamp"] + c["slippage"] + c["levy"]


def turnover_cost(delta_position, rate: float):
    """换仓成本 = |仓位变化| × 对应方向费率"""
    return delta_position.abs() * rate


def directional_cost(delta_position, settings):
    """按方向计成本：加仓用买入费率，减仓用卖出费率；可设单笔最低佣金"""
    delta = delta_position
    buy = delta.clip(lower=0) * buy_rate(settings)
    sell = (-delta).clip(lower=0) * sell_rate(settings)
    cost = buy + sell
    mc = float(settings.get("backtest", {}).get("cost", {}).get("min_commission", 0.0))
    if mc > 0:
        traded = delta.abs() > 0
        cost = cost.where(~(traded & (cost < mc)), mc)
    return cost


def cost_breakeven_analysis(results, min_sharpe=0.5,
                            robust_band=(None, 1.8),
                            acceptable_band=(1.8, 2.4)) -> dict:
    """成本盈亏平衡分析（25 号）：

    results：[{factor, annualized_return, sharpe, max_drawdown, ...}]
    按成本乘数判定：
        < 1.8×  → 稳健（Robust）
        1.8–2.4× → 可接受（Acceptable）
        > 2.4×  → 失效（Broken）

    失效判定：annualized_return ≤ 0 或 sharpe < min_sharpe。
    """
    rows = []
    broken_at = None
    for r in sorted(results, key=lambda x: float(x.get("factor", 1.0))):
        factor = float(r.get("factor", 1.0))
        ret = float(r.get("annualized_return") or 0.0)
        sharpe = float(r.get("sharpe") or 0.0)
        failed = ret <= 0.0 or sharpe < float(min_sharpe)
        if failed and broken_at is None:
            broken_at = factor
        if factor < robust_band[1]:
            band = "Robust"
        elif factor < acceptable_band[1]:
            band = "Acceptable"
        else:
            band = "Broken" if failed else "Degraded"
        rows.append({"factor": factor, "annualized_return": round(ret, 4),
                     "sharpe": round(sharpe, 4),
                     "max_drawdown": round(float(r.get("max_drawdown") or 0.0),
                                           4),
                     "band": band, "failed": failed})
    if broken_at is not None:
        if broken_at < robust_band[1]:
            verdict = "FRAGILE"
        elif broken_at < acceptable_band[1]:
            verdict = "ACCEPTABLE_WITH_LIMIT"
        else:
            verdict = "ROBUST_TO_COST"
    else:
        verdict = "ROBUST_TO_COST"
    return {"rows": rows, "break_even_factor": broken_at,
            "verdict": verdict}
