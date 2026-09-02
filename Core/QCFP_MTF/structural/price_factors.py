# coding: utf-8
"""P 因子（季度价格）

输入：hk_hist_quarterly_kline + hk_hist_daily_kline（52W 位置）
输出：q_return / q_trend_score / q_position_52w + p_state（P↑/P→/P↓）
"""

import numpy as np
import pandas as pd

from ..common.normalization import pctl_rank


def _compute_52w_position(q_df: pd.DataFrame, daily_df: pd.DataFrame) -> pd.Series:
    """季末快照：日线 252 交易日窗口的 52 周位置；日线不足时回退季度 5 期"""
    pos = pd.Series(np.nan, index=q_df.index)
    daily_by_stock = {code: g.sort_values("date") for code, g in daily_df.groupby("stock_code")}
    q_grp = q_df.sort_values(["stock_code", "date"])

    for stock, g in q_grp.groupby("stock_code"):
        daily = daily_by_stock.get(stock)
        q_dates = g["date"].values
        for idx, q_end in zip(g.index, q_dates):
            if pd.isna(g.loc[idx, "close"]):
                continue
            if daily is not None and len(daily):
                closes = daily.loc[daily["date"] <= q_end, "close"].dropna()
                closes = closes.tail(252)
                if len(closes) >= 20:
                    lo, hi = closes.min(), closes.max()
                    if hi > lo:
                        pos.loc[idx] = (g.loc[idx, "close"] - lo) / (hi - lo)
                        continue
            # 回退：季度滚动 5 期
            g_sorted = g.sort_values("date")
            gpos = g_sorted.index.get_loc(idx)
            window = g_sorted["close"].iloc[max(0, gpos - 4): gpos + 1].dropna()
            if len(window) >= 3:
                lo, hi = window.min(), window.max()
                if hi > lo:
                    pos.loc[idx] = (g_sorted.loc[idx, "close"] - lo) / (hi - lo)
    return pos


def _macd_score(dif, signal, hist):
    if pd.isna(dif) or pd.isna(signal):
        return np.nan
    if not pd.isna(hist) and hist > 0 and dif > signal:
        return 100.0
    if dif > signal:
        return 60.0
    return 20.0


def build_p_factors(q_df: pd.DataFrame, daily_df: pd.DataFrame, settings: dict) -> pd.DataFrame:
    """计算 P 因子

    Args:
        q_df: hk_hist_quarterly_kline（经 loader 标准化，含 ema/macd 列）
        daily_df: hk_hist_daily_kline（52W 位置用）
        settings: QCFP 配置 dict
    """
    st = settings.get("structural", {})
    thr = st.get("direction_thresholds", {})
    p_thr = float(thr.get("p_return_threshold", 2.0))
    p_flat = float(thr.get("p_flat_return", 1.0))
    weights = st.get("trend_score_weights", {})

    df = q_df[["stock_code", "stock_name", "date", "close", "volume", "amount",
               "ema5", "ema10", "ema20", "ema50",
               "macd_dif", "macd_signal", "macd_histogram"]].copy()
    df["period_end"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")

    # 负价格/零成交量占位数据清洗
    invalid = (df["close"] <= 0)
    for col in ["close", "ema5", "ema10", "ema20", "ema50"]:
        df.loc[invalid, col] = np.nan

    df = df.sort_values(["stock_code", "date"]).reset_index(drop=True)
    df["prev_close"] = df.groupby("stock_code")["close"].shift(1)
    df["q_return"] = (df["close"] / df["prev_close"] - 1.0) * 100.0

    # 52W 位置（季末快照）
    df["q_position_52w"] = _compute_52w_position(df, daily_df)

    # ---- q_trend_score 组件 ----
    # 1) 同期收益百分位（横截面 0~100）
    df["_quarter"] = pd.to_datetime(df["period_end"]).dt.to_period("Q").astype(str)
    df["return_pctl"] = df.groupby("_quarter")["q_return"].transform(
        lambda s: pctl_rank(s) * 100.0)
    # 2) 均线排列分
    ma = ((df["ema5"] > df["ema10"]).astype(float) +
          (df["ema10"] > df["ema20"]).astype(float) +
          (df["ema20"] > df["ema50"]).astype(float))
    df["ma_alignment"] = ma.where(df["ema50"].notna()) * 100.0 / 3.0
    # 3) MACD 状态分
    df["macd_state"] = [
        _macd_score(d, s, h)
        for d, s, h in zip(df["macd_dif"], df["macd_signal"], df["macd_histogram"])
    ]
    # 4) 52W 位置分
    df["position_score"] = df["q_position_52w"] * 100.0
    # 5) VWAP 偏离分
    df["vwap_q"] = df["amount"] / df["volume"].replace(0, np.nan)
    df["vwap_dev"] = (df["close"] / df["vwap_q"] - 1.0).clip(-0.20, 0.20)
    df["vwap_score"] = (df["vwap_dev"] + 0.20) / 0.40 * 100.0

    # 加权合成（可用组件重新归一化权重）
    comps = {"return_pctl": 1, "ma_alignment": 1, "macd_state": 1,
             "position_score": 1, "vwap_score": 1}
    wmap = {"return_pctl": "return_pctl", "ma_alignment": "ma_alignment",
            "macd_state": "macd_state", "position_score": "position_52w",
            "vwap_score": "vwap_deviation"}
    total_w = sum(weights.get(k, 0) for k in wmap.values())
    if total_w <= 0:
        df["q_trend_score"] = np.nan
    else:
        acc = pd.Series(0.0, index=df.index)
        used_w = 0.0
        for col, wkey in wmap.items():
            w = float(weights.get(wkey, 0))
            if w <= 0:
                continue
            acc = acc + df[col].fillna(0.0) * w
            used_w += w
        df["q_trend_score"] = (acc / used_w).where(
            df[list(comps)].notna().any(axis=1))

    # ---- p_state ----
    def _p_state(r):
        if pd.isna(r["q_return"]):
            return None
        if r["q_return"] > p_thr:
            return "P↑"
        if r["q_return"] < -p_thr:
            return "P↓"
        return "P→"

    df["p_state"] = df.apply(_p_state, axis=1)
    df["p_flat_flag"] = df["q_return"].abs() < p_flat

    df["quarter"] = df["_quarter"].str.replace("Q", "/Q", regex=False)
    cols = ["stock_code", "stock_name", "quarter", "period_end",
            "q_return", "q_trend_score", "q_position_52w",
            "p_state", "p_flat_flag"]
    return df[cols].reset_index(drop=True)
