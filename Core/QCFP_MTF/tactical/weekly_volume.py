# coding: utf-8
"""周量检测：放量突破 / 极度缩量（相对 MA20）"""

import pandas as pd

from ..common.normalization import rolling_mean


def build_volume_factors(w_df: pd.DataFrame, settings: dict) -> pd.DataFrame:
    cfg = settings.get("tactical", {}).get("volume", {})
    ma_w = int(cfg.get("ma_window", 20))
    breakout_ratio = float(cfg.get("breakout_ratio", 1.8))
    shrink_ratio = float(cfg.get("shrink_ratio", 0.5))

    df = w_df[["stock_code", "date", "volume"]].copy()
    df["week_end"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df = df.sort_values(["stock_code", "date"]).reset_index(drop=True)
    df["w_volume_ma"] = df.groupby("stock_code")["volume"].transform(
        lambda s: rolling_mean(s, window=ma_w, min_periods=10))
    df["w_volume_ratio"] = df["volume"] / df["w_volume_ma"]
    df["w_volume_breakout"] = (
        (df["w_volume_ratio"] >= breakout_ratio).where(df["w_volume_ma"].notna(), 0).astype(int))
    df["w_volume_shrink"] = (
        (df["w_volume_ratio"] <= shrink_ratio).where(df["w_volume_ma"].notna(), 0).astype(int))
    return df[["stock_code", "week_end", "w_volume_ratio",
               "w_volume_breakout", "w_volume_shrink"]].reset_index(drop=True)
