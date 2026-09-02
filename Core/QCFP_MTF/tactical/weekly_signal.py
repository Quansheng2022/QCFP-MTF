# coding: utf-8
"""周线战术信号：均线斜率 + 突破/破位 + 4 种信号合成"""

import pandas as pd


def build_signal(w_df: pd.DataFrame, vol_f: pd.DataFrame, vwap_f: pd.DataFrame,
                 settings: dict) -> pd.DataFrame:
    cfg_ma = settings.get("tactical", {}).get("ma", {})
    lag = int(cfg_ma.get("slope_lag", 2))
    thr_pct = float(cfg_ma.get("slope_threshold_pct", 0.5))
    lookback = int(settings.get("tactical", {}).get("breakout", {}).get("lookback", 20))

    df = w_df[["stock_code", "date", "close", "high", "low", "ema5", "ema10", "ema20"]].copy()
    df["week_end"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df = df.sort_values(["stock_code", "date"]).reset_index(drop=True)
    g = df.groupby("stock_code")

    # 均线二阶差分（加速/减速）
    df["ema5_d2"] = df["ema5"] - 2 * df.groupby("stock_code")["ema5"].shift(1) \
        + df.groupby("stock_code")["ema5"].shift(lag)

    def _slope(r):
        if pd.isna(r["ema5_d2"]) or pd.isna(r["close"]) or r["close"] == 0:
            return None
        rel = r["ema5_d2"] / r["close"] * 100.0
        if rel > thr_pct:
            return "加速"
        if rel < -thr_pct:
            return "减速"
        return "平稳"

    df["w_ma_slope"] = df.apply(_slope, axis=1)

    # 突破/破位：前 N 周高低（不含当期）作为基准
    df["prior_high"] = g["high"].transform(
        lambda s: s.rolling(lookback, min_periods=10).max().shift(1))
    df["prior_low"] = g["low"].transform(
        lambda s: s.rolling(lookback, min_periods=10).min().shift(1))

    merged = df.merge(vol_f[["stock_code", "week_end", "w_volume_breakout"]],
                      on=["stock_code", "week_end"], how="left") \
        .merge(vwap_f[["stock_code", "week_end", "w_vwap_deviation"]],
               on=["stock_code", "week_end"], how="left")
    merged["_vwap"] = merged["close"] / (1 + merged["w_vwap_deviation"])

    merged["w_breakout"] = (
        (merged["close"] > merged["prior_high"]) &
        (merged["w_volume_breakout"] == 1) &
        (merged["close"] > merged["_vwap"])
    ).where(merged["prior_high"].notna(), False).astype(int)
    merged["w_breakdown"] = (
        (merged["close"] < merged["prior_low"]) &
        (merged["close"] < merged["_vwap"])
    ).where(merged["prior_low"].notna(), False).astype(int)

    def _signal(r):
        if r["w_breakdown"] == 1:
            return "Breakdown"
        if r["w_breakout"] == 1:
            return "Breakout"
        if pd.notna(r["ema5"]) and pd.notna(r["ema20"]) \
                and r["close"] < r["ema5"] and r["close"] > r["ema20"]:
            return "Pullback"
        return "Consolidation"

    merged["tactical_signal"] = merged.apply(_signal, axis=1)
    cols = ["stock_code", "week_end", "w_ma_slope", "w_breakout",
            "w_breakdown", "tactical_signal"]
    return merged[cols].reset_index(drop=True)
