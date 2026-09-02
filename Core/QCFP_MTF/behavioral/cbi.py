# coding: utf-8
"""CBI（Chip Behavior Index）筹码行为指数

规格书 5.1：Raw Factor → Winsorize(1%~99%) → Z-Score → 0~100 → Weighted Sum
CBI = 30%×N(1/Turnover_Std12) + 30%×N(1-Pctl12) + 25%×N(1/Volume_Std12) + 15%×N(1/Amplitude_MA6)
"""

import numpy as np
import pandas as pd

from ..common.normalization import (rolling_mean, rolling_pctl, rolling_std,
                                    scale_0_100, winsorize, zscore)


def _safe_inverse(s: pd.Series) -> pd.Series:
    """1/x；x=0（如 std=0 的完全稳定序列）用有限值中的高分位填充"""
    inv = 1.0 / s
    finite = inv[np.isfinite(inv)]
    fill = float(finite.quantile(0.99)) if len(finite) else np.nan
    return inv.where(np.isfinite(inv), fill)


def _xs_standardize(s: pd.Series, groups: pd.Series, min_n: int = 3) -> pd.Series:
    """横截面 as-of 标准化：同一 month_end 内 Winsorize→Z→0~100

    只使用当月全部股票观测，不涉及未来数据（月度数据月末已知）。
    组内有效样本 < min_n 时返回 NaN（由调用方回退）。
    """
    def _norm(x: pd.Series) -> pd.Series:
        if x.notna().sum() < min_n:
            return pd.Series(np.nan, index=x.index)
        return scale_0_100(zscore(winsorize(x)))

    return s.groupby(groups).transform(_norm)


def _expanding_per_stock(s: pd.Series, stock: pd.Series,
                         min_periods: int = 12) -> pd.Series:
    """个股 expanding 标准化（仅用截至当期历史，无未来泄漏）

    作为横截面样本不足时的回退方案。
    """
    def _exp(sv: pd.Series) -> pd.Series:
        lo = sv.expanding(min_periods).quantile(0.01)
        hi = sv.expanding(min_periods).quantile(0.99)
        clipped = sv.clip(lower=lo, upper=hi)
        mean = clipped.expanding(min_periods).mean()
        std = clipped.expanding(min_periods).std(ddof=0).replace(0, np.nan)
        z = (clipped - mean) / std
        mn = z.expanding(min_periods).min()
        mx = z.expanding(min_periods).max()
        span = (mx - mn)
        out = ((z - mn) / span * 100.0).where(span > 0, 50.0)
        return out.where(sv.notna())

    return s.groupby(stock).transform(_exp)


def _norm_component(series: pd.Series, month: pd.Series, stock: pd.Series) -> pd.Series:
    """组件标准化：优先横截面（当月），样本不足回退个股 expanding"""
    xs = _xs_standardize(series, month)
    missing = xs.isna() & series.notna()
    if missing.any():
        fb = _expanding_per_stock(series, stock)
        xs = xs.mask(missing, fb)
    return xs


def build_cbi(m_df: pd.DataFrame, settings: dict) -> pd.DataFrame:
    weights = settings.get("cbi_weights", {})
    w_turn_stab = float(weights.get("turnover_stability", 0.30))
    w_turn_pctl = float(weights.get("turnover_pctl_inverse", 0.30))
    w_vol_stab = float(weights.get("volume_stability", 0.25))
    w_amp_stab = float(weights.get("amplitude_stability", 0.15))
    state_cfg = settings.get("thresholds", {}).get("cbi", {})
    locked = float(state_cfg.get("locked", 70))
    stable = float(state_cfg.get("stable", 50))
    active = float(state_cfg.get("active", 30))

    df = m_df[["stock_code", "date", "turnover_rate", "volume", "amplitude"]].copy()
    df["month_end"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df["turnover_rate"] = df["turnover_rate"].where(df["turnover_rate"] > 0)
    df["volume"] = df["volume"].where(df["volume"] > 0)
    df = df.sort_values(["stock_code", "date"]).reset_index(drop=True)
    g = df.groupby("stock_code")

    t_std = g["turnover_rate"].transform(lambda s: rolling_std(s, 12, 6))
    v_std = g["volume"].transform(lambda s: rolling_std(s, 12, 6))
    amp_ma = g["amplitude"].transform(lambda s: rolling_mean(s, 6, 2))
    t_pctl = g["turnover_rate"].transform(lambda s: rolling_pctl(s, 12, 6))

    # as-of 标准化：横截面（当月）优先，样本不足回退个股 expanding（均无未来泄漏）
    month = df["month_end"]
    stock = df["stock_code"]
    n_turn_stab = _norm_component(_safe_inverse(t_std), month, stock)
    n_turn_pctl = _norm_component(1.0 - t_pctl, month, stock)
    n_vol_stab = _norm_component(_safe_inverse(v_std), month, stock)
    n_amp_stab = _norm_component(_safe_inverse(amp_ma), month, stock)

    df["cbi_score"] = (w_turn_stab * n_turn_stab + w_turn_pctl * n_turn_pctl
                       + w_vol_stab * n_vol_stab + w_amp_stab * n_amp_stab)
    df["_cbi_has_data"] = df[["turnover_rate", "volume"]].notna().any(axis=1)

    def _state(score):
        if pd.isna(score):
            return None
        if score > locked:
            return "CBI_LOCKED_CANDIDATE"
        if score >= stable:
            return "CBI_STABLE"
        if score >= active:
            return "CBI_ACTIVE"
        return "CBI_TURBULENT"

    df["cbi_state"] = df["cbi_score"].map(_state)
    return df[["stock_code", "month_end", "cbi_score", "cbi_state"]].reset_index(drop=True)
