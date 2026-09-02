# coding: utf-8
"""市场环境分层稳健性 + 参数稳定性曲面（QCFP-MTF 2.8）

27 号：不能只报告"最佳参数=17"，而要输出 Parameter Stability Surface
与 Stable Region——相邻参数绩效是否平缓（稳定区域），还是尖峰（过拟合）。
"""

import pandas as pd

from .performance import evaluate


def by_market_regime(pnl, regime, turnover=None, annual_periods: int = 52) -> pd.DataFrame:
    rows = []
    for regime_name in ["risk_on", "neutral", "risk_off"]:
        mask = regime == regime_name
        g_turn = turnover[mask] if turnover is not None else None
        rows.append({"market_regime": regime_name,
                     **evaluate(pnl[mask], turnover=g_turn,
                                annual_periods=annual_periods)})
    rows.append({"market_regime": "ALL",
                 **evaluate(pnl, turnover=turnover,
                            annual_periods=annual_periods)})
    return pd.DataFrame(rows)


def parameter_stability_surface(sweep: list, metric="sharpe",
                                plateau_tolerance=0.15) -> dict:
    """参数稳定性曲面（27 号）。

    sweep：[{param: value, sharpe: ..., annualized_return: ..., ...}]
    输出：
        surface          每个参数点的指标（原始表）
        best_param       最高指标参数
        stable_region    稳定参数区间（相邻点指标不低于最优 ×(1−tolerance)）
        stability_score  0-100（曲面平缓度：1 − 归一化峰谷差）
        verdict          STABLE / PEAKY（尖峰 = 过拟合可疑）
    """
    rows = [dict(r) for r in sweep]
    if not rows:
        return {"surface": [], "best_param": None, "stable_region": [],
                "stability_score": 0.0, "verdict": "UNKNOWN"}
    vals = [float(r.get(metric) or 0.0) for r in rows]
    best_idx = max(range(len(rows)), key=lambda i: vals[i])
    best_param = rows[best_idx].get("param")
    best_val = vals[best_idx]
    floor = best_val * (1.0 - float(plateau_tolerance))
    stable = [i for i, v in enumerate(vals) if v >= floor]
    # 稳定区间：连续块
    blocks = []
    cur = []
    for i in range(len(rows)):
        if i in stable:
            cur.append(i)
        elif cur:
            blocks.append(cur)
            cur = []
    if cur:
        blocks.append(cur)
    stable_region = [
        {"start_param": rows[b[0]].get("param"),
         "end_param": rows[b[-1]].get("param"),
         "n_points": len(b)}
        for b in blocks]
    spread = max(vals) - min(vals) if len(vals) > 1 else 0.0
    mean = sum(vals) / len(vals) if vals else 1.0
    stability = max(0.0, min(100.0, (1.0 - spread / max(abs(mean), 1e-9))
                             * 100.0))
    # 尖峰判定：最优与相邻均值差 > 30% 且稳定区间窄
    neighbors = [vals[i] for i in (best_idx - 1, best_idx + 1)
                 if 0 <= i < len(rows)]
    neighbor_mean = sum(neighbors) / len(neighbors) if neighbors else 0.0
    peaky = bool(neighbors and best_val > neighbor_mean * 1.3
                 and max((len(b) for b in blocks), default=0) <= 1)
    return {
        "surface": rows,
        "best_param": best_param,
        "best_value": round(best_val, 4),
        "stable_region": stable_region,
        "stability_score": round(stability, 2),
        "verdict": "PEAKY" if peaky else "STABLE",
    }
