# coding: utf-8
"""Performance Metric Contract（QCFP-MTF 2.8：11 号统一指标层）

所有研究模块（Backtest/Ablation/Stress/Report）只能调用本层，
统一口径：
    equity_curve → CAGR / Total Return / Vol / Sharpe / Sortino / MDD /
    Calmar / Turnover / Cost / Win Rate

规则：
    - arithmetic return 与 compounded return 不混用
    - 日/周/月频率统一 annualization
    - 无风险利率一致
    - Transaction Cost 计入一致
    - NaN/缺失样本规则一致
"""

import math


def annualization_factor(period="weekly") -> float:
    return {"daily": 252, "weekly": 52, "monthly": 12}.get(
        str(period or "weekly").lower(), 52)


def equity_metrics(returns, period="weekly", rf=0.02,
                   turnover=None, cost=None) -> dict:
    """标准指标层：同一组 trades 无论进入哪个模块结果一致。"""
    import numpy as np
    r = np.asarray([float(x) for x in returns], float)
    r = r[~np.isnan(r)]                    # NaN 一致剔除
    ann = annualization_factor(period)
    n = len(r)
    if n == 0:
        return {"n": 0}
    # compounded total / CAGR
    equity = np.cumprod(1 + r)
    total_return = float(equity[-1] - 1.0)
    years = n / ann
    cagr = (equity[-1] ** (1 / years) - 1.0) if years > 0 and equity[-1] > 0 \
        else None
    mean = float(r.mean())
    sd = float(r.std(ddof=1)) if n > 1 else 0.0
    rf_per = rf / ann
    excess = mean - rf_per
    sharpe = excess / sd * math.sqrt(ann) if sd > 0 else None
    downside = r[r < rf_per]
    dd_sd = float(np.std(downside - rf_per, ddof=1)) \
        if len(downside) > 1 else 0.0
    sortino = excess / dd_sd * math.sqrt(ann) if dd_sd > 0 else None
    peak = np.maximum.accumulate(equity)
    mdd = float((equity / peak - 1).min())
    calmar = cagr / abs(mdd) if mdd < 0 and cagr is not None else None
    win_rate = float((r > 0).mean())
    return {
        "n": n,
        "total_return": round(total_return, 6),
        "cagr": round(cagr, 6) if cagr is not None else None,
        "annualized_vol": round(sd * math.sqrt(ann), 6),
        "sharpe": round(sharpe, 6) if sharpe is not None else None,
        "sortino": round(sortino, 6) if sortino is not None else None,
        "max_drawdown": round(mdd, 6),
        "calmar": round(calmar, 6) if calmar is not None else None,
        "turnover": round(float(turnover or 0.0), 6),
        "cost": round(float(cost or 0.0), 6),
        "win_rate": round(win_rate, 6),
        "period": str(period), "rf": float(rf),
        "annualization": ann,
    }
