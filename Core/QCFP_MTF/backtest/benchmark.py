# coding: utf-8
"""Benchmark / 超额收益

- buy_hold：等权持有全部股票（无择时）的周收益
- hsi：恒指周收益（按策略周对齐）
- excess：策略组合收益 - 基准（年化 alpha + 信息比率 IR）
"""

import numpy as np
import pandas as pd


def buy_hold_returns(weekly_df) -> pd.Series:
    """等权全股票买入持有周收益（index=week_end）"""
    df = weekly_df[["stock_code", "date", "close"]].copy()
    df["week_end"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df = df.sort_values(["stock_code", "week_end"])
    df["ret"] = df.groupby("stock_code")["close"].pct_change()
    return df.groupby("week_end")["ret"].mean().dropna()


def hsi_returns(idx_df, week_ends) -> pd.Series:
    """恒指周收益（按给定周对齐）"""
    idx = idx_df[["date", "HSI"]].copy()
    idx["date"] = pd.to_datetime(idx["date"])
    idx = idx.sort_values("date").dropna(subset=["HSI"])
    idx["hsi_ret"] = idx["HSI"].pct_change()
    asof = pd.DataFrame({"date": pd.to_datetime(list(week_ends))}).sort_values("date")
    m = pd.merge_asof(asof, idx, on="date", direction="backward")
    m["week_end"] = pd.DatetimeIndex(m["date"]).strftime("%Y-%m-%d")
    return m.set_index("week_end")["hsi_ret"].dropna()


def excess_stats(strategy_pnl: pd.Series, benchmark: pd.Series,
                 annual_periods: int = 52) -> dict:
    """策略相对基准的超额收益统计（P0 修正，不再把复合主动收益称为 alpha）

    同时输出：
        strategy_cagr / benchmark_cagr / cagr_spread（CAGR 差）
        active_annualized（算术主动收益 = mean(strategy-bench)×52）
        information_ratio / correlation
    excess_annualized 保留为 cagr_spread（严格口径）。
    """
    df = pd.DataFrame({"strategy": strategy_pnl, "bench": benchmark}).dropna()
    if len(df) < 5:
        return {"n": 0, "strategy_cagr": np.nan, "benchmark_cagr": np.nan,
                "cagr_spread": np.nan, "active_annualized": np.nan,
                "excess_annualized": np.nan, "information_ratio": np.nan,
                "correlation": np.nan}
    n = len(df)
    excess = df["strategy"] - df["bench"]
    mean = excess.mean()
    std = excess.std(ddof=0)
    ir = float(mean / std * np.sqrt(annual_periods)) if std and std > 0 else np.nan
    strat_cagr = float((1 + df["strategy"]).prod() ** (annual_periods / n) - 1)
    bench_cagr = float((1 + df["bench"]).prod() ** (annual_periods / n) - 1)
    active_ann = float(mean * annual_periods)
    corr = float(df["strategy"].corr(df["bench"]))
    return {"n": int(len(df)),
            "strategy_cagr": round(strat_cagr, 6),
            "benchmark_cagr": round(bench_cagr, 6),
            "cagr_spread": round(strat_cagr - bench_cagr, 6),
            "active_annualized": round(active_ann, 6),
            "excess_annualized": round(strat_cagr - bench_cagr, 6),
            "information_ratio": round(ir, 4) if ir == ir else None,
            "correlation": round(corr, 4) if corr == corr else None}


def momentum_top_n(weekly_df, top_n: int = 5, lookback: int = 13,
                   start=None, end=None) -> pd.Series:
    """价格动量基准：每周末按过去 lookback 周收益选 Top-N，等权，T+1 生效

    用于检验 QCFP Top-N 的超额是否只是动量/小盘偏差。
    Returns: 周收益 Series（index=week_end）
    """
    df = weekly_df[["stock_code", "date", "close"]].copy()
    df["week_end"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df = df.sort_values(["stock_code", "week_end"])
    df["mom"] = df.groupby("stock_code")["close"].transform(
        lambda s: s.shift(1) / s.shift(lookback + 1) - 1.0)
    df["ret"] = df.groupby("stock_code")["close"].pct_change()
    if start:
        df = df[df["week_end"] >= start]
    if end:
        df = df[df["week_end"] <= end]

    rows = []
    for week, g in df.groupby("week_end"):
        top = g.dropna(subset=["mom"]).sort_values("mom", ascending=False).head(top_n)
        rows.append((week, set(top["stock_code"])))
    # 组合在 T 周末形成，T+1 周收益生效
    weights = {}
    for i, (week, stocks) in enumerate(rows):
        if i == 0:
            weights[week] = set()
        else:
            weights[week] = rows[i - 1][1]
    out = []
    for week, held in weights.items():
        r = df[(df["week_end"] == week) & (df["stock_code"].isin(held))]["ret"]
        out.append({"week_end": week, "momentum_return": float(r.mean()) if len(r) else 0.0})
    s = pd.DataFrame(out).set_index("week_end")["momentum_return"]
    return s
