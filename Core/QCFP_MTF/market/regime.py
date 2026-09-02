# coding: utf-8
"""Market Regime（QCFP-MTF 2.7：Regime-aware 参数管理）

5 态 Regime：Bull / Bear / Sideway / HighVolatility / Crisis
不同 Regime 使用不同 Wave Trigger / Entry / Risk Cap / Holding 参数，
减少"一个阈值在不同市场环境下失效"的问题。
"""

import numpy as np


def classify_regime(idx_df, date, lookback=60,
                    vol_threshold=0.25, crisis_dd=0.20) -> str:
    """基于指数趋势 + 波动率 + 回撤分类（as-of，仅用 <= date 数据）"""
    import pandas as pd
    df = idx_df.copy()
    if "date" not in df.columns or df.empty:
        return "Sideway"
    df["date"] = pd.to_datetime(df["date"])
    df = df[df["date"] <= pd.Timestamp(date)].sort_values("date")
    if df.empty:
        return "Sideway"
    close = df["close"] if "close" in df.columns else \
        (df["HSI"] if "HSI" in df.columns else None)
    if close is None:
        return "Sideway"
    c = close.astype(float).to_numpy()
    if len(c) < 20:
        return "Sideway"
    w = c[-min(lookback, len(c)):]
    ret = w[-1] / w[0] - 1 if w[0] > 0 else 0.0
    vol = float(np.std(np.diff(np.log(w))) * np.sqrt(52))
    drawdown = c[-1] / np.maximum.accumulate(c) - 1
    dd = float(drawdown[-1])
    if dd <= -crisis_dd or (ret <= -0.15 and vol > vol_threshold):
        return "Crisis"
    if vol > vol_threshold:
        return "HighVolatility"
    if ret > 0.05:
        return "Bull"
    if ret < -0.05:
        return "Bear"
    return "Sideway"


def regime_scale(regime, settings, key="risk_cap") -> float:
    """按 Regime 取参数缩放（settings.regime_params.<regime>.<key>，缺省 1.0）"""
    params = (settings or {}).get("regime_params", {}).get(regime, {})
    return float(params.get(key, 1.0))
