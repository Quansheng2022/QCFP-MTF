# coding: utf-8
"""周换手检测：季度周均偏离 + 极端换手（MA8×2.0）"""

import pandas as pd

from ..common.normalization import rolling_mean


def build_turnover_factors(w_df: pd.DataFrame, settings: dict) -> pd.DataFrame:
    cfg = settings.get("tactical", {}).get("turnover", {})
    q_w = int(cfg.get("quarter_window", 13))
    spike_w = int(cfg.get("spike_ma_window", 8))
    spike_ratio = float(cfg.get("spike_ratio", 2.0))

    df = w_df[["stock_code", "date", "turnover_rate"]].copy()
    df["week_end"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df = df.sort_values(["stock_code", "date"]).reset_index(drop=True)
    g = df.groupby("stock_code")["turnover_rate"]
    df["w_turnover_quarter_ma"] = g.transform(lambda s: rolling_mean(s, window=q_w, min_periods=8))
    df["w_turnover_spike_ma"] = g.transform(lambda s: rolling_mean(s, window=spike_w, min_periods=4))
    df["w_turnover_deviation"] = df["turnover_rate"] / df["w_turnover_quarter_ma"] - 1.0
    df["w_turnover_spike"] = (
        (df["turnover_rate"] >= df["w_turnover_spike_ma"] * spike_ratio)
        .where(df["w_turnover_spike_ma"].notna(), 0).astype(int))
    return df[["stock_code", "week_end", "w_turnover_deviation",
               "w_turnover_spike"]].reset_index(drop=True)
