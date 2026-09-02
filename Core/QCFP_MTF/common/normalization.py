# coding: utf-8
"""标准化工具：Winsorize -> Z-Score -> 0~100 缩放（规格书 5.1 CBI 标准化流程）"""

import numpy as np
import pandas as pd


def winsorize(series: pd.Series, lower: float = 0.01, upper: float = 0.99) -> pd.Series:
    """1%~99% 分位数截尾（Winsorize），NaN 保留"""
    s = series.astype(float)
    valid = s.dropna()
    if valid.empty:
        return s
    lo = valid.quantile(lower)
    hi = valid.quantile(upper)
    return s.clip(lower=lo, upper=hi)


def zscore(series: pd.Series) -> pd.Series:
    """Z-Score 标准化（均值 0，标准差 1）；std=0 时返回 0"""
    s = series.astype(float)
    mean = s.mean()
    std = s.std(ddof=0)
    if std is None or np.isnan(std) or std == 0:
        return pd.Series(0.0, index=s.index)
    return (s - mean) / std


def scale_0_100(series: pd.Series, lower=None, upper=None) -> pd.Series:
    """Min-Max 缩放到 0~100；区间长度为 0 时返回 50"""
    s = series.astype(float)
    lo = s.min() if lower is None else float(lower)
    hi = s.max() if upper is None else float(upper)
    if hi - lo == 0 or pd.isna(hi) or pd.isna(lo):
        return pd.Series(50.0, index=s.index)
    return (s - lo) / (hi - lo) * 100.0


def standardize_0_100(series: pd.Series,
                      winsor_lower: float = 0.01,
                      winsor_upper: float = 0.99) -> pd.Series:
    """完整流水线：Winsorize -> Z-Score -> 0~100（规格书 5.1）"""
    return scale_0_100(zscore(winsorize(series, winsor_lower, winsor_upper)))


def pctl_rank(series: pd.Series) -> pd.Series:
    """百分位排名（0~1），升序"""
    s = series.astype(float)
    if s.notna().sum() == 0:
        return s
    return s.rank(pct=True)


def rolling_zscore(series: pd.Series,
                   window: int = 8,
                   min_history: int = 3) -> pd.Series:
    """当前值相对窗口内历史（不含当前）的 Z-Score

    历史样本 < min_history 或 std=0 时返回 NaN / 0。
    """
    def _f(w: np.ndarray) -> float:
        if len(w) < min_history + 1:
            return np.nan
        hist = w[:-1]
        std = hist.std(ddof=0)
        if std == 0 or np.isnan(std):
            return 0.0
        return float((w[-1] - hist.mean()) / std)

    return series.rolling(window, min_periods=min_history + 1).apply(_f, raw=True)


def rolling_pctl(series: pd.Series,
                 window: int = 12,
                 min_periods: int = 6) -> pd.Series:
    """当前值在滚动窗口内的百分位（0~1，升序）"""
    def _f(w: np.ndarray) -> float:
        if len(w) < min_periods:
            return np.nan
        rank = float((w <= w[-1]).sum())
        return rank / len(w)

    return series.rolling(window, min_periods=min_periods).apply(_f, raw=True)


def rolling_std(series: pd.Series, window: int = 12, min_periods: int = 6) -> pd.Series:
    """滚动标准差（NaN 安全）"""
    return series.rolling(window, min_periods=min_periods).std(ddof=0)


def rolling_mean(series: pd.Series, window: int = 6, min_periods: int = 2) -> pd.Series:
    return series.rolling(window, min_periods=min_periods).mean()
