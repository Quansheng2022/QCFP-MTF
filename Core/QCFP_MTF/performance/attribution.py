# coding: utf-8
"""P&L Attribution（QCFP-MTF 2.8：28 号收益来源归因）

回答"QCFP_MTF 到底在选对机会、少亏钱，还是进出更好"：
    Total P&L → Market Beta / Wave / Entry Timing / Sizing / Exit Timing /
                 Regime / Sector / Risk Avoidance / Execution Cost / Slippage
    → 归类 Alpha / Beta / Timing / Sizing / Risk Avoidance / Execution

数据充足时做完整分解；字段缺失时退化到可计算子集，并如实标注
"归因覆盖度"（attribution_coverage）。
"""

import numpy as np


def _cov(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    if len(x) < 2 or np.std(x) == 0:
        return 0.0
    return float(np.cov(x, y)[0, 1])


def _var(x):
    x = np.asarray(x, float)
    return float(np.var(x)) if len(x) > 1 else 0.0


def market_beta_contribution(portfolio_returns, benchmark_returns) -> float:
    """Beta 贡献 = beta × 市场平均收益（组合对市场的暴露收益）。"""
    p = np.asarray(portfolio_returns, float)
    b = np.asarray(benchmark_returns, float)
    if len(p) == 0 or len(b) != len(p):
        return 0.0
    beta = _cov(p, b) / (_var(b) + 1e-12)
    return float(beta * np.mean(b))


def timing_contribution(trades, key="entry_delay_weeks") -> float:
    """进出场时机贡献：延迟越久，净收益损失越大（负向）。"""
    delays = [float(t.get(key) or 0.0) for t in trades]
    rets = [float(t.get("net_return") or 0.0) for t in trades]
    if not delays:
        return 0.0
    return round(-float(np.mean([d * r for d, r in zip(delays, rets)])),
                 4)


def sizing_contribution(trades) -> float:
    """仓位贡献：加权收益 - 等权收益（暴露集中在好机会 = 正贡献）。"""
    if not trades:
        return 0.0
    weights = [float(t.get("exposure") or 0.0) for t in trades]
    rets = [float(t.get("net_return") or 0.0) for t in trades]
    w = np.array(weights)
    if w.sum() <= 0:
        return 0.0
    weighted = float(np.dot(w / w.sum(), rets))
    equal = float(np.mean(rets))
    return round(weighted - equal, 4)


def wave_contribution(trades, setup_key="setup_type",
                      strong_setups=("BREAKOUT", "PULLBACK", "RECOVERY")) -> float:
    """波段选择贡献：强 Setup 组合收益 - 全体平均（选对机会）。"""
    if not trades:
        return 0.0
    strong = [float(t.get("net_return") or 0.0) for t in trades
              if t.get(setup_key) in strong_setups]
    all_ = [float(t.get("net_return") or 0.0) for t in trades]
    if not strong:
        return 0.0
    return round(float(np.mean(strong)) - float(np.mean(all_)), 4)


def regime_contribution(trades, regime_key="regime",
                        favorable=("Bull", "Recovery")) -> float:
    """环境贡献：有利 Regime 组合收益 - 全体平均。"""
    if not trades:
        return 0.0
    fav = [float(t.get("net_return") or 0.0) for t in trades
           if t.get(regime_key) in favorable]
    all_ = [float(t.get("net_return") or 0.0) for t in trades]
    if not fav:
        return 0.0
    return round(float(np.mean(fav)) - float(np.mean(all_)), 4)


def risk_avoidance_contribution(blocked_trades) -> float:
    """风险规避贡献：被 BLOCK 掉的交易如果做了会亏多少（负数 = 少亏即正贡献）。"""
    if not blocked_trades:
        return 0.0
    avoided = [float(t.get("net_return") or 0.0) for t in blocked_trades]
    return round(-float(np.mean(avoided)), 4)


def execution_contribution(trades) -> float:
    """执行成本贡献：毛收益 - 净收益的合计（负向）。"""
    if not trades:
        return 0.0
    g = sum(float(t.get("gross_return") or float(t.get("net_return") or 0.0))
            for t in trades)
    n = sum(float(t.get("net_return") or 0.0) for t in trades)
    return round(g - n, 4)


def portfolio_allocation_alpha(trades, score_key="opportunity_score") -> float:
    """组合配置 Alpha（68 号）：排名价值——
    按机会分排序后，高分半组实际收益 − 低分半组（资金给对机会的溢价）。"""
    scored = [t for t in trades if t.get(score_key) is not None]
    if len(scored) < 4:
        return 0.0
    scored = sorted(scored, key=lambda t: -float(t[score_key]))
    half = len(scored) // 2
    top = [float(t.get("net_return") or 0.0) for t in scored[:half]]
    bottom = [float(t.get("net_return") or 0.0) for t in scored[half:]]
    return round(sum(top) / len(top) - sum(bottom) / len(bottom), 4)


def attribution_report(portfolio_returns=None, benchmark_returns=None,
                       trades=None, blocked_trades=None,
                       sector_contribution=0.0, slippage_contribution=0.0,
                       total_return=None) -> dict:
    """完整归因报告。

    分解项：
        market_beta / wave / entry_timing / sizing / exit_timing /
        regime / sector / risk_avoidance / execution_cost / slippage / alpha
    归类：
        Beta（market_beta）/ Timing（entry+exit）/ Sizing / Wave（wave+regime）
        Risk Avoidance / Execution（execution+slippage）/ Alpha（残差）
    """
    trades = trades or []
    blocked = blocked_trades or []
    if total_return is None:
        total_return = float(np.sum(
            [float(t.get("net_return") or 0.0) for t in trades]))
    beta = market_beta_contribution(
        portfolio_returns or [], benchmark_returns or [])
    entry_t = timing_contribution(trades, "entry_delay_weeks")
    exit_t = timing_contribution(trades, "exit_delay_weeks")
    sizing = sizing_contribution(trades)
    wave = wave_contribution(trades)
    regime = regime_contribution(trades)
    risk_avoid = risk_avoidance_contribution(blocked)
    execution = execution_contribution(trades)
    portfolio_alloc = portfolio_allocation_alpha(trades)
    explained = (beta + wave + entry_t + sizing + exit_t + regime
                 + float(sector_contribution or 0.0) + risk_avoid
                 + execution + float(slippage_contribution or 0.0)
                 + portfolio_alloc)
    alpha = round(float(total_return) - explained, 4)
    buckets = {
        "Beta": round(beta, 4),
        "Wave": round(wave + regime, 4),
        "Timing": round(entry_t + exit_t, 4),
        "Sizing": round(sizing, 4),
        "Portfolio_Allocation": round(portfolio_alloc, 4),
        "Risk_Avoidance": round(risk_avoid, 4),
        "Execution": round(execution + float(slippage_contribution or 0.0), 4),
        "Alpha": alpha,
    }
    return {
        "total_return": round(float(total_return), 4),
        "decomposition": {
            "market_beta": round(beta, 4),
            "wave": round(wave, 4),
            "entry_timing": round(entry_t, 4),
            "sizing": round(sizing, 4),
            "exit_timing": round(exit_t, 4),
            "regime": round(regime, 4),
            "sector": round(float(sector_contribution or 0.0), 4),
            "risk_avoidance": round(risk_avoid, 4),
            "execution_cost": round(execution, 4),
            "slippage": round(float(slippage_contribution or 0.0), 4),
            "portfolio_allocation": round(portfolio_alloc, 4),
            "alpha": alpha,
        },
        "buckets": buckets,
        "n_trades": len(trades),
        "n_blocked": len(blocked),
    }


def attribution_to_md(report: dict) -> str:
    """归因报告 → Markdown 表格。"""
    d = report["decomposition"]
    lines = [
        f"# P&L Attribution Report",
        "",
        f"**Total Return：{report['total_return']:+.2%}**",
        f"（trades={report['n_trades']}，blocked={report['n_blocked']}）",
        "",
        "| 来源 | 贡献 | 归类 |",
        "| --- | --- | --- |",
    ]
    mapping = [
        ("market_beta", "Beta"),
        ("wave", "Wave"),
        ("entry_timing", "Timing"),
        ("sizing", "Sizing"),
        ("exit_timing", "Timing"),
        ("regime", "Wave"),
        ("sector", "Sector"),
        ("risk_avoidance", "Risk_Avoidance"),
        ("execution_cost", "Execution"),
        ("slippage", "Execution"),
        ("alpha", "Alpha"),
    ]
    for key, bucket in mapping:
        lines.append(f"| {key} | {d[key]:+.2%} | {bucket} |")
    lines += ["", "## 归类汇总", "", "| 归类 | 合计 |", "| --- | --- |"]
    for k, v in report["buckets"].items():
        lines.append(f"| {k} | {v:+.2%} |")
    return "\n".join(lines)
