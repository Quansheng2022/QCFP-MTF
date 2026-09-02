# coding: utf-8
"""Market Regime × Strategy Performance Matrix（QCFP-MTF 2.8：37 号）

回答"不同市场状态下 QCFP_MTF 表现如何"：
    Regime → Trades / Win Rate / Return / MDD / Sharpe / Expectancy
并做 Permission × Regime × Wave 交互分析
（如 ALLOW+STRONG 在 Bull 有效、Transition 中胜率下降）。
"""


def regime_strategy_matrix(trades) -> dict:
    """trades：[{regime, permission, wave_strength, net_return, mfe,
    mae}] → 每 Regime 绩效 + 交互摘要。"""
    from collections import defaultdict
    by_regime = defaultdict(list)
    for t in trades:
        by_regime[t.get("regime") or "unknown"].append(t)
    matrix = {}
    for regime, group in by_regime.items():
        rets = [float(t.get("net_return") or 0.0) for t in group]
        wins = sum(1 for r in rets if r > 0)
        equity = 1.0
        peak = 1.0
        mdd = 0.0
        for r in rets:
            equity *= (1 + r)
            peak = max(peak, equity)
            mdd = min(mdd, equity / peak - 1)
        mean = sum(rets) / len(rets)
        sd = (sum((r - mean) ** 2 for r in rets) / len(rets)) ** 0.5
        matrix[regime] = {
            "trades": len(group),
            "win_rate": round(wins / len(group), 4),
            "return": round(sum(rets), 4),
            "mdd": round(mdd, 4),
            "sharpe": round(mean / sd * 52 ** 0.5, 4) if sd > 0 else None,
            "expectancy": round(mean, 4),
        }
    # Permission × Regime × Wave 交互
    interaction = defaultdict(list)
    for t in trades:
        key = (t.get("permission") or "?", t.get("regime") or "?",
               "STRONG" if float(t.get("wave_strength") or 0.0) >= 0.6
               else "WEAK")
        interaction[key].append(float(t.get("net_return") or 0.0))
    interaction_summary = {
        k: {"n": len(v),
            "mean_return": round(sum(v) / len(v), 4)}
        for k, v in interaction.items()}
    return {"matrix": matrix, "interaction": interaction_summary}
