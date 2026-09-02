# coding: utf-8
"""换手-流动性因子（T1~T5）

输入：hk_hist_monthly_kline.turnover_rate
输出：m_turnover_zscore / m_turnover_pctl / m_turnover_ma_ratio
      + turnover_liquidity_regime（T1~T5）
"""

import numpy as np
import pandas as pd

from ..common.normalization import rolling_mean, rolling_pctl, rolling_zscore


def _t_from_z(z: float, bands) -> str:
    if z < bands[0]:
        return "T1"
    if z < bands[1]:
        return "T2"
    if z <= bands[2]:
        return "T3"
    if z <= bands[3]:
        return "T4"
    return "T5"


def build_turnover_factors(m_df: pd.DataFrame, settings: dict) -> pd.DataFrame:
    """计算月线换手因子与 T1~T5 状态"""
    cfg = settings.get("behavioral", {}).get("turnover", {})
    window = int(cfg.get("window", 12))
    min_hist = int(cfg.get("min_history", 5))
    pctl_min = int(cfg.get("pctl_min_history", 6))
    z_bands = [float(x) for x in cfg.get("z_bands", [-1.5, -0.5, 0.5, 1.5])]

    df = m_df[["stock_code", "stock_name", "date", "turnover_rate"]].copy()
    df["month_end"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    # 停牌/零换手月置 NaN
    df["turnover_rate"] = df["turnover_rate"].where(df["turnover_rate"] > 0)
    df = df.sort_values(["stock_code", "date"]).reset_index(drop=True)
    g = df.groupby("stock_code")

    df["m_turnover_zscore"] = g["turnover_rate"].transform(
        lambda s: rolling_zscore(s, window=window, min_history=min_hist))
    df["m_turnover_pctl"] = g["turnover_rate"].transform(
        lambda s: rolling_pctl(s, window=window, min_periods=pctl_min))
    df["m_turnover_ma_ratio"] = g["turnover_rate"].transform(
        lambda s: s / rolling_mean(s, window=6, min_periods=3))

    df["turnover_liquidity_regime"] = df["m_turnover_zscore"].map(
        lambda z: _t_from_z(z, z_bands) if pd.notna(z) else None)
    # 当月数据缺失（停牌/零换手）时因子整体置 NaN，不做滚动回算
    missing = df["turnover_rate"].isna()
    df.loc[missing, ["m_turnover_zscore", "m_turnover_pctl",
                     "m_turnover_ma_ratio", "turnover_liquidity_regime"]] = np.nan

    cols = ["stock_code", "stock_name", "month_end",
            "m_turnover_zscore", "m_turnover_pctl", "m_turnover_ma_ratio",
            "turnover_liquidity_regime"]
    return df[cols].reset_index(drop=True)
