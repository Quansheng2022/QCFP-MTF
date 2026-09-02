# coding: utf-8
"""组合层风险管理指标：VaR / 年化波动 / 回撤 / 暴露度"""

import numpy as np
import pandas as pd


def portfolio_risk(returns: pd.Series, exposure: pd.Series = None,
                   annual_periods: int = 52) -> dict:
    r = returns.dropna()
    if r.empty:
        return {"n": 0, "var95": np.nan, "annualized_vol": np.nan,
                "max_drawdown": np.nan, "avg_exposure": np.nan,
                "cash_ratio": np.nan}
    var95 = float(np.percentile(r, 5))
    vol = float(r.std(ddof=0) * np.sqrt(annual_periods))
    eq = (1 + r).cumprod()
    mdd = float((eq / eq.cummax() - 1).min())
    avg_exp = float(exposure.mean()) if exposure is not None else np.nan
    cash = 1.0 - avg_exp if avg_exp == avg_exp else np.nan
    return {
        "n": int(len(r)),
        "var95": round(var95, 6),
        "annualized_vol": round(vol, 6),
        "max_drawdown": round(mdd, 6),
        "avg_exposure": round(avg_exp, 4) if avg_exp == avg_exp else None,
        "cash_ratio": round(cash, 4) if cash == cash else None,
    }
