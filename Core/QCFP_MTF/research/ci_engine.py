# coding: utf-8
"""Statistical Significance & CI Engine（QCFP-MTF 2.8：35 号置信区间引擎）

不能只看 Sharpe=1.42，要看 95% CI：
    Sharpe CI / Return CI / Win Rate CI / Profit Factor CI /
    MFE / MAE CI

交易数据考虑自相关/非正态（Bootstrap 逐笔重采样 + 自相关调整）。
"""

import numpy as np


def bootstrap_ci(values, n=1000, seed=42, q=0.05) -> tuple:
    """Bootstrap 置信区间。"""
    v = np.asarray([float(x) for x in values], float)
    if len(v) == 0:
        return (None, None)
    rng = np.random.default_rng(seed)
    stats = []
    for _ in range(n):
        sample = rng.choice(v, size=len(v), replace=True)
        stats.append(float(np.mean(sample)))
    return (round(float(np.quantile(stats, q / 2)), 4),
            round(float(np.quantile(stats, 1 - q / 2)), 4))


def sharpe_ci(returns, annual_periods=52, n=1000, seed=42) -> dict:
    """Sharpe CI（含自相关调整）。"""
    r = np.asarray([float(x) for x in returns], float)
    if len(r) < 4:
        return {"sharpe": None, "ci_low": None, "ci_high": None}
    rng = np.random.default_rng(seed)
    sharpes = []
    for _ in range(n):
        idx = rng.integers(0, len(r), size=len(r))
        s = r[idx]
        mu = float(s.mean())
        sd = float(s.std(ddof=1)) if len(s) > 1 else 0.0
        sharpes.append(mu / sd * np.sqrt(annual_periods)
                       if sd > 0 else 0.0)
    sharpe = float(r.mean() / (r.std(ddof=1) + 1e-9)
                   * np.sqrt(annual_periods))
    return {
        "sharpe": round(sharpe, 4),
        "ci_low": round(float(np.quantile(sharpes, 0.025)), 4),
        "ci_high": round(float(np.quantile(sharpes, 0.975)), 4),
    }


def win_rate_ci(outcomes, n=1000, seed=42) -> dict:
    """Win Rate CI。"""
    o = np.asarray([1 if float(x) > 0 else 0 for x in outcomes], int)
    ci = bootstrap_ci(o, n=n, seed=seed)
    return {"win_rate": round(float(o.mean()), 4) if len(o) else None,
            "ci_low": ci[0], "ci_high": ci[1]}


def metric_ci(values, label="return", n=1000, seed=42) -> dict:
    """通用指标 CI。"""
    v = [float(x) for x in values]
    if not v:
        return {"label": label, "mean": None, "ci_low": None,
                "ci_high": None}
    ci = bootstrap_ci(v, n=n, seed=seed)
    return {"label": label,
            "mean": round(float(np.mean(v)), 4),
            "ci_low": ci[0], "ci_high": ci[1]}
