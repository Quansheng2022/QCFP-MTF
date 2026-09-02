# coding: utf-8
"""绩效评估：年化收益、夏普、最大回撤、胜率、盈亏比、分年度"""

import numpy as np
import pandas as pd


def evaluate(pnl: pd.Series, position: pd.Series = None,
             annual_periods: int = 52, rf: float = 0.0,
             turnover: pd.Series = None) -> dict:
    """对 pnl 序列做绩效评估

    Args:
        pnl: 周期收益序列
        position: 对应仓位序列（用于统计持仓期胜率）；None 时用 pnl 非零
        annual_periods: 每年周期数（周=52）
        rf: 无风险利率（年化）
        turnover: 周期换手序列（用于年化换手）
    """
    pnl = pnl.dropna()
    n = len(pnl)
    if n == 0:
        return {"n": 0, "total_return": np.nan, "annualized_return": np.nan,
                "sharpe": np.nan, "max_drawdown": np.nan, "win_rate": np.nan,
                "profit_factor": np.nan, "sortino": np.nan, "calmar": np.nan,
                "annual_turnover": np.nan}
    total = float((1 + pnl).prod() - 1)
    ann = float((1 + total) ** (annual_periods / n) - 1) if n > 0 else np.nan

    if position is None:
        positioned = pnl
    else:
        positioned = pnl[position.fillna(0) > 0]

    mean = pnl.mean()
    std = pnl.std(ddof=0)
    sharpe = float((mean - rf / annual_periods) / std * np.sqrt(annual_periods)) \
        if std and std > 0 else np.nan
    # P1：标准 downside deviation = sqrt(mean(min(r - target, 0)^2))
    target_r = rf / annual_periods
    downside = np.minimum(pnl - target_r, 0.0)
    down_dev = float(np.sqrt((downside ** 2).mean())) if len(pnl) else np.nan
    sortino = float((mean - target_r) / down_dev * np.sqrt(annual_periods)) \
        if down_dev and down_dev > 0 else np.nan

    eq = (1 + pnl).cumprod()
    max_dd = float((eq / eq.cummax() - 1).min())
    calmar = float(ann / abs(max_dd)) if max_dd and max_dd != 0 else np.nan
    win_rate = float((positioned > 0).mean()) if len(positioned) else np.nan
    gains = positioned[positioned > 0].sum()
    losses = -positioned[positioned < 0].sum()
    profit_factor = float(gains / losses) if losses and losses > 0 else np.nan
    annual_turnover = float(turnover.mean() * annual_periods) \
        if turnover is not None and len(turnover) else np.nan

    return {
        "n": int(n),
        "total_return": round(total, 6),
        "annualized_return": round(ann, 6),
        "sharpe": round(sharpe, 4),
        "max_drawdown": round(max_dd, 6),
        "win_rate": round(win_rate, 4) if win_rate == win_rate else None,
        "positive_week_rate": round(win_rate, 4) if win_rate == win_rate else None,
        "profit_factor": round(profit_factor, 4) if profit_factor == profit_factor else None,
        "sortino": round(sortino, 4) if sortino == sortino else None,
        "calmar": round(calmar, 4) if calmar == calmar else None,
        "annual_turnover": round(annual_turnover, 4) if annual_turnover == annual_turnover else None,
    }


def by_year(pnl: pd.Series, index_dates) -> pd.DataFrame:
    """分年度绩效表"""
    s = pnl.copy()
    s.index = pd.to_datetime(index_dates)
    rows = []
    for year, g in s.groupby(s.index.year):
        rows.append({"year": year, **evaluate(g)})
    return pd.DataFrame(rows)
