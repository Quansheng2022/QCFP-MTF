# coding: utf-8
"""量因子

输入：hk_hist_monthly_kline.volume / turnover_rate
输出：m_volume_ma_ratio / m_volume_accel + vol_dir / turn_dir（供 VP 矩阵）
"""

import numpy as np
import pandas as pd

from ..common.normalization import rolling_mean


def _direction(ratio, up, down, strong):
    if pd.isna(ratio):
        return None
    if ratio >= strong:
        return "↑↑"
    if ratio >= up:
        return "↑"
    if ratio <= down:
        return "↓"
    return "→"


def build_volume_factors(m_df: pd.DataFrame, settings: dict) -> pd.DataFrame:
    cfg = settings.get("behavioral", {}).get("volume", {})
    ma_w = int(cfg.get("ma_window", 6))
    lag = int(cfg.get("accel_lag", 3))
    up = float(cfg.get("up_ratio", 1.10))
    down = float(cfg.get("down_ratio", 0.90))
    strong = float(cfg.get("strong_ratio", 1.50))

    df = m_df[["stock_code", "date", "volume", "turnover_rate"]].copy()
    df["month_end"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df["volume"] = df["volume"].where(df["volume"] > 0)
    df["turnover_rate"] = df["turnover_rate"].where(df["turnover_rate"] > 0)
    df = df.sort_values(["stock_code", "date"]).reset_index(drop=True)
    g = df.groupby("stock_code")

    df["m_volume_ma_ratio"] = g["volume"].transform(
        lambda s: s / rolling_mean(s, window=ma_w, min_periods=3))
    df["m_volume_accel"] = g["volume"].transform(lambda s: s / s.shift(lag) - 1.0)
    df["_turnover_ma_ratio"] = g["turnover_rate"].transform(
        lambda s: s / rolling_mean(s, window=ma_w, min_periods=3))

    df["vol_dir"] = df["m_volume_ma_ratio"].map(lambda r: _direction(r, up, down, strong))
    df["turn_dir"] = df["_turnover_ma_ratio"].map(lambda r: _direction(r, up, down, strong))
    # 当月数据缺失时因子整体置 NaN
    df.loc[df["volume"].isna(), ["m_volume_ma_ratio", "m_volume_accel", "vol_dir"]] = np.nan
    df.loc[df["turnover_rate"].isna(), "turn_dir"] = np.nan

    cols = ["stock_code", "month_end", "m_volume_ma_ratio", "m_volume_accel",
            "vol_dir", "turn_dir"]
    return df[cols].reset_index(drop=True)
