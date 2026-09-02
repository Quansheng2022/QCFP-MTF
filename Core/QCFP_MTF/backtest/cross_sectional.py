# coding: utf-8
"""横截面股票池回测：每周末按评分排序选 Top-N，等权（按 risk 仓位缩放）

时间模型与主回测一致：T 周信号 → T+1 周持仓 → T+1 周收益
（权重按股票滞后一周，杜绝"用本周收益评价本周末才形成的选股"）。
"""

import numpy as np
import pandas as pd

from .cost_model import directional_cost


def _weekly_returns(weekly_df):
    df = weekly_df[["stock_code", "date", "close"]].copy()
    df["week_end"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df = df.sort_values(["stock_code", "week_end"])
    df["ret"] = df.groupby("stock_code")["close"].pct_change()
    return df[["stock_code", "week_end", "ret"]].reset_index(drop=True)


def cross_sectional_portfolio(signals, weekly_df, settings, top_n=None,
                              score_threshold=None, score_col="qcfp_score",
                              min_amount=0.0, start=None, end=None) -> pd.DataFrame:
    """每周按评分排序选股并组合（T 周选股 → T+1 周收益）

    Args:
        signals: data_pipeline 输出（含 qcfp_score / target / mtf_regime）
        weekly_df: 周 K 线
        top_n: 每期持股数（None 时用 score_threshold 筛选）
        score_threshold: 入选最低评分（None 时用 top_n）
        score_col: 排序评分列（默认 qcfp_score；增量实验可传自定义列）
        min_amount: 最小周成交额（HKD），低于剔除（流动性过滤）
    Returns:
        DataFrame: week_end / n_selected / portfolio_return / turnover / equity
    """
    if score_col not in signals.columns:
        raise ValueError(f"信号表缺少评分列: {score_col}")
    s = signals[["stock_code", "decision_date", score_col, "target"]].copy()
    s = s.rename(columns={score_col: "score"})
    s = s.rename(columns={"decision_date": "week_end"})
    # P0：完整 stock × 交易周 网格来自周 K 日历（而非 signal∩return），
    # 显式区分 signal_missing / return_missing，绝不用 fillna(0) 掩盖缺数据。
    ret_all = _weekly_returns(weekly_df)
    if start:
        ret_all = ret_all[ret_all["week_end"] >= start]
    if end:
        ret_all = ret_all[ret_all["week_end"] <= end]
    if min_amount and min_amount > 0:
        amt = weekly_df[["stock_code", "date", "amount"]].copy()
        amt["week_end"] = pd.to_datetime(amt["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        amt = amt.groupby(["stock_code", "week_end"], as_index=False)["amount"].sum()
        ret_all = ret_all.merge(amt, on=["stock_code", "week_end"], how="left")
        ret_all = ret_all[ret_all["amount"].fillna(0) >= min_amount]
    if ret_all.empty:
        return pd.DataFrame()

    # 每周末权重：按评分排序选股；target 是"单股票目标暴露"，
    # 组合权重 = target / N（组合总暴露 = 入选股 target 均值），
    # 不允许把 target 重新归一化到 100%（P0：修复 target 语义）。
    def _weights(g):
        g = g.sort_values("score", ascending=False)
        if top_n:
            g = g.head(top_n)
        elif score_threshold is not None:
            g = g[g["score"] >= score_threshold]
        if g.empty:
            return g[["stock_code", "week_end", "score"]].assign(w=0.0)
        w_raw = g["target"].clip(lower=0).fillna(0.0)
        w = w_raw / max(len(g), 1)
        return g[["stock_code", "week_end", "score"]].assign(w=w)

    weeks = sorted(ret_all["week_end"].unique())
    stocks = sorted(ret_all["stock_code"].unique())
    full = pd.DataFrame({
        "stock_code": np.repeat(stocks, len(weeks)),
        "week_end": np.tile(weeks, len(stocks)),
    })
    full = full.merge(s[["stock_code", "week_end", "score", "target"]],
                      on=["stock_code", "week_end"], how="left")
    full = full.merge(ret_all[["stock_code", "week_end", "ret"]],
                      on=["stock_code", "week_end"], how="left")
    n_signal_missing = int(full["score"].isna().sum())
    n_return_missing = int(full["ret"].isna().sum())
    wts = []
    for week, g in full.groupby("week_end"):
        wts.append(_weights(g[g["score"].notna()]))
    weights = pd.concat(wts, ignore_index=True)
    full = full.merge(weights[["stock_code", "week_end", "w"]],
                      on=["stock_code", "week_end"], how="left")
    full["w"] = full["w"].fillna(0.0)
    full = full.sort_values(["stock_code", "week_end"])

    # T 周形成的组合 → T+1 周才持仓（严格按完整网格逐周 shift）
    full["w_eff"] = full.groupby("stock_code")["w"].shift(1).fillna(0.0)
    full["prev_w"] = full.groupby("stock_code")["w_eff"].shift(1).fillna(0.0)
    full["dw"] = full["w_eff"] - full["prev_w"]
    full["contrib"] = full["w_eff"] * full["ret"]

    # 方向成本：加仓用买入费率，减仓用卖出费率（真实方向成本，可含单笔最低佣金）
    full["cost"] = directional_cost(full["dw"], settings)

    # P0：缺失收益 ≠ 整周删除——仅剔除该周缺失收益的持仓股（保留周与其余股票）；
    # 若整周无任何有效持仓收益，则该周标记缺失（不 fillna(0)，不改变年化分母口径之外的样本）。
    n_missing_stock_weeks = int(((full["w_eff"] > 0) & full["ret"].isna()).sum())
    clean = full[~((full["w_eff"] > 0) & full["ret"].isna())]
    week_counts = clean.groupby("week_end")["contrib"].count()
    empty_weeks = set(clean["week_end"].unique()) - set(week_counts[week_counts > 0].index)
    clean = clean[~clean["week_end"].isin(empty_weeks)]
    missing_weeks = empty_weeks
    agg = clean.groupby("week_end").agg(
        portfolio_return=("contrib", "sum"),
        gross_turnover=("dw", lambda x: x.abs().sum()),
        cost=("cost", "sum"),
        n_selected=("w_eff", lambda x: int((x > 0).sum())),
    ).reset_index()
    # P0-3 修复：turnover 必须是毛换手（权重变化绝对值和），不能与成本混淆
    agg["turnover"] = agg["gross_turnover"]
    agg["portfolio_return"] = (agg["portfolio_return"] - agg["cost"]).round(8)
    out = agg[["week_end", "n_selected", "portfolio_return", "turnover", "gross_turnover"]]
    out["equity"] = (1 + out["portfolio_return"]).cumprod()
    out.attrs["coverage"] = {
        "n_signal_missing": n_signal_missing,
        "n_return_missing": n_return_missing,
        "n_missing_stock_weeks": n_missing_stock_weeks,
        "n_missing_return_weeks": len(missing_weeks),
    }
    return out
