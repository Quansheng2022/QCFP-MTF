# coding: utf-8
"""日线战术层（L4 · Tactical Timing）

定位：Q/M/W 决定"能不能做、什么方向"；Daily 只负责"什么时候做"。
Daily 无权改变 Quarterly/Monthly/Weekly 状态，只输出波段阶段：
    DAILY_ACCUMULATION / DAILY_BREAKOUT / DAILY_PULLBACK / DAILY_DISTRIBUTION /
    DAILY_DECLINE / DAILY_NEUTRAL

因子口径：F + P 为主，C 不使用（日频机构持仓不可得）。
PIT 规则：只用 T 日及之前的数据，T+1 才可执行（所有滚动窗口均 shift(1)）。
"""

import numpy as np
import pandas as pd


def build_price_factors(d_df: pd.DataFrame, settings: dict) -> pd.DataFrame:
    """价格+量因子：均线、趋势评分、量比、20 日 VWAP、前 N 日高低、突破/派发/回调候选"""
    cfg = settings.get("daily", {}).get("tactical", {})
    lookback = int(cfg.get("breakout_lookback", 20))
    vol_break = float(cfg.get("breakout_volume_ratio", 1.5))
    vol_stall = float(cfg.get("stall_volume_ratio", 1.2))
    near_high = float(cfg.get("near_high_ratio", 0.98))
    df = d_df[["stock_code", "date", "open", "high", "low", "close",
               "volume", "amount"]].copy()
    df = df.sort_values(["stock_code", "date"]).reset_index(drop=True)
    g = df.groupby("stock_code")

    df["d_ma5"] = g["close"].transform(lambda s: s.rolling(5, min_periods=3).mean())
    df["d_ma10"] = g["close"].transform(lambda s: s.rolling(10, min_periods=5).mean())
    df["d_ma20"] = g["close"].transform(lambda s: s.rolling(20, min_periods=8).mean())
    # 趋势评分 0~100：价格站上 MA20 + MA5>MA10 + MA10>MA20
    df["d_trend_score"] = (
        (df["close"] > df["d_ma20"]).astype(float)
        + (df["d_ma5"] > df["d_ma10"]).astype(float)
        + (df["d_ma10"] > df["d_ma20"]).astype(float)
    ) / 3.0 * 100.0
    df["d_vol_ratio"] = df["volume"] / g["volume"].transform(
        lambda s: s.rolling(5, min_periods=3).mean().shift(1))
    # 20 日 VWAP（PIT：截至当日累计额/量）
    df["_cum_amt"] = g["amount"].cumsum()
    df["_cum_vol"] = g["volume"].cumsum()
    df["_vwap20"] = (
        df["_cum_amt"].rolling(20, min_periods=8).sum()
        / df["_cum_vol"].rolling(20, min_periods=8).sum())
    df["d_prior_high"] = g["high"].transform(
        lambda s: s.rolling(lookback, min_periods=10).max().shift(1))
    df["d_prior_low"] = g["low"].transform(
        lambda s: s.rolling(lookback, min_periods=10).min().shift(1))
    df["d_near_high"] = (df["close"] / df["d_prior_high"]).where(df["d_prior_high"].notna())
    df["_ret"] = g["close"].transform(lambda s: s.pct_change())

    df["d_breakout"] = (
        (df["close"] > df["d_prior_high"]) &
        (df["d_vol_ratio"] >= vol_break) &
        (df["close"] > df["_vwap20"])
    ).where(df["d_prior_high"].notna(), False).astype(int)
    # 派发候选：接近前高 + 放量滞涨 + 仍在 MA20 上方
    df["d_distribution"] = (
        (df["d_near_high"] >= near_high) &
        (df["d_vol_ratio"] >= vol_stall) &
        (df["_ret"] <= 0.005) &
        (df["close"] > df["d_ma20"])
    ).where(df["d_near_high"].notna(), False).astype(int)
    # 回调候选：中期趋势向上（MA10>MA20 且价格在 MA20 上），短期回调（跌破 MA5 或 MA5<MA10）
    df["d_pullback"] = (
        (df["d_ma10"] > df["d_ma20"]) &
        (df["close"] >= df["d_ma20"]) &
        ((df["close"] < df["d_ma5"]) | (df["d_ma5"] < df["d_ma10"]))
    ).fillna(False).astype(int)

    cols = ["stock_code", "date", "d_ma5", "d_ma10", "d_ma20", "d_trend_score",
            "d_vol_ratio", "d_prior_high", "d_near_high", "close", "d_breakout",
            "d_distribution", "d_pullback"]
    return df[cols].reset_index(drop=True)


def build_flow_factors(mf_df: pd.DataFrame, settings: dict):
    """日资金流因子：机构净流入代理（超大单+大单净额）、60 日 PIT Z、5 日改善斜率

    注：历史表以 extra_large/large（按单净额）为主，capital_in/out_* 仅近期有值；
    优先用 extra_large+large，缺失时回退 capital_in/out 差额。
    """
    if mf_df is None or mf_df.empty:
        return None
    cfg = settings.get("daily", {}).get("tactical", {})
    win = int(cfg.get("flow_z_window", 60))
    df = mf_df.copy()
    if {"extra_large", "large"}.issubset(df.columns):
        df["_net"] = df["extra_large"] + df["large"]
    else:
        df["_net"] = None
    if {"capital_in_super", "capital_in_big",
        "capital_out_super", "capital_out_big"}.issubset(mf_df.columns):
        alt = (df["capital_in_super"] + df["capital_in_big"]
               - df["capital_out_super"] - df["capital_out_big"])
        df["_net"] = df["_net"].fillna(alt)
    df["d_inst_flow"] = df["_net"]
    g = df.groupby("stock_code")

    def _z(s):
        mean = s.rolling(win, min_periods=20).mean().shift(1)
        std = s.rolling(win, min_periods=20).std().shift(1)
        std = std.replace(0, np.nan)   # 恒定资金流 → Z 视为缺失而非无穷
        return (s - mean) / std

    df["d_flow_z"] = g["d_inst_flow"].transform(_z)
    df["d_flow_ma5"] = g["d_inst_flow"].transform(
        lambda s: s.rolling(5, min_periods=3).mean().shift(1))
    df["d_flow_slope"] = (
        g["d_inst_flow"].transform(lambda s: s.rolling(5, min_periods=3).mean().shift(1))
        - g["d_inst_flow"].transform(lambda s: s.rolling(20, min_periods=10).mean().shift(1)))
    cols = ["stock_code", "date", "d_inst_flow", "d_flow_z", "d_flow_ma5", "d_flow_slope"]
    return df[cols].reset_index(drop=True)


def build_daily_states(p_f: pd.DataFrame, f_f, settings: dict) -> pd.DataFrame:
    """合成日线战术状态：BREAKOUT > DISTRIBUTION > PULLBACK > ACCUMULATION > NEUTRAL"""
    cfg = settings.get("daily", {}).get("tactical", {})
    flow_thr = float(cfg.get("accum_flow_z", 0.2))
    df = p_f.copy()
    has_flow = f_f is not None and not f_f.empty
    if has_flow:
        df = df.merge(f_f, on=["stock_code", "date"], how="left")

    if has_flow:
        df["d_accumulation"] = (
            (df["d_breakout"] == 0) &
            (df["d_distribution"] == 0) &
            (df["d_flow_z"] > flow_thr) &
            (df["d_flow_slope"] > 0) &
            (df["d_vol_ratio"] >= 0.7) &
            (df["d_vol_ratio"] <= 2.0) &
            (df["close"] <= df["d_prior_high"])
        ).where(df["d_prior_high"].notna(), False).astype(int)
    else:
        # 无资金流数据（2021 前）：以价格+量结构近似（趋势改善 + 缩量整理）
        df["d_accumulation"] = (
            (df["d_breakout"] == 0) &
            (df["d_distribution"] == 0) &
            (df["d_vol_ratio"] <= 0.8) &
            (df["d_trend_score"] >= 33.3)
        ).astype(int)

    # DAILY_DECLINE：持续下降（close<MA20 且 MA5<MA10；有资金流时要求 flow_z<0）
    df["d_decline"] = (
        (df["close"] < df["d_ma20"]) & (df["d_ma5"] < df["d_ma10"])
    ).fillna(False).astype(int)
    if has_flow:
        df["d_decline"] = (df["d_decline"] == 1) & (df["d_flow_z"] < 0)
        df["d_decline"] = df["d_decline"].astype(int)

    def _state(r):
        if int(r["d_breakout"]) == 1:
            return "DAILY_BREAKOUT"
        if int(r["d_distribution"]) == 1:
            return "DAILY_DISTRIBUTION"
        if int(r["d_decline"]) == 1:
            return "DAILY_DECLINE"
        if int(r["d_pullback"]) == 1:
            return "DAILY_PULLBACK"
        if int(r["d_accumulation"]) == 1:
            return "DAILY_ACCUMULATION"
        return "DAILY_NEUTRAL"

    df["daily_state"] = df.apply(_state, axis=1)
    df["d_breakout"] = df["d_breakout"].astype(int)
    df["d_distribution"] = df["d_distribution"].astype(int)
    df["d_decline"] = df["d_decline"].astype(int)
    df["d_pullback"] = df["d_pullback"].astype(int)
    df["d_accumulation"] = df["d_accumulation"].astype(int)
    df["trade_date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    keep = ["stock_code", "trade_date", "daily_state", "d_breakout",
            "d_distribution", "d_pullback", "d_accumulation", "d_decline", "d_trend_score",
            "d_vol_ratio", "d_near_high"]
    if has_flow:
        keep += ["d_inst_flow", "d_flow_z", "d_flow_slope"]
    else:
        df["d_inst_flow"] = None
        df["d_flow_z"] = None
        df["d_flow_slope"] = None
        keep += ["d_inst_flow", "d_flow_z", "d_flow_slope"]
    return df[keep].reset_index(drop=True)
