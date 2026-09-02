# coding: utf-8
"""扩展窗口（Expanding Window）交叉验证"""

import pandas as pd

from .engine import portfolio_returns, run_backtest
from .performance import evaluate


def expanding_windows(start: str, end: str, step_days: int = 365) -> list:
    """生成 [(label, w_start, w_end)]；w_start 固定为 start，w_end 逐步扩展"""
    s = pd.Timestamp(start)
    e = pd.Timestamp(end)
    anchors = []
    cur = s + pd.Timedelta(days=step_days * 2)
    while cur <= e:
        anchors.append(cur)
        cur += pd.Timedelta(days=step_days)
    if not anchors:
        anchors = [e]
    return [(f"{s:%Y%m%d}-{a:%Y%m%d}", s.strftime("%Y-%m-%d"), a.strftime("%Y-%m-%d"))
            for a in anchors]


def run_expanding(signals, weekly_df, settings, start, end,
                  step_days=365, annual_periods=52) -> pd.DataFrame:
    rows = []
    for label, ws, we in expanding_windows(start, end, step_days):
        bt = run_backtest(signals, weekly_df, settings, start=ws, end=we)
        port = portfolio_returns(bt)
        rows.append({"window": label, "window_start": ws, "window_end": we,
                     **evaluate(port["portfolio_return"],
                                turnover=port["avg_turnover"],
                                annual_periods=annual_periods)})
    return pd.DataFrame(rows)


def walk_forward_windows(start: str, end: str,
                         train_years: int = 2, test_years: int = 1) -> list:
    """Walk-forward 切分：[(label, train_start, train_end, test_start, test_end)]"""
    s = pd.Timestamp(start)
    e = pd.Timestamp(end)
    rows = []
    train_end = s + pd.DateOffset(years=train_years)
    while train_end < e:
        test_end = min(train_end + pd.DateOffset(years=test_years), e)
        label = f"{s:%Y%m%d}-{test_end:%Y%m%d}"
        rows.append((label,
                     s.strftime("%Y-%m-%d"), train_end.strftime("%Y-%m-%d"),
                     train_end.strftime("%Y-%m-%d"), test_end.strftime("%Y-%m-%d")))
        train_end = test_end
    return rows


def rolling_oos_evaluation(signals, weekly_df, settings, start, end,
                           step_days=365, annual_periods=52) -> pd.DataFrame:
    """Rolling OOS Evaluation：固定默认参数，分测试窗滚动评价组合绩效

    注意：这是 OOS 滚动评价（固定参数），不是 train→calibrate→test 的
    参数 Walk-forward（后者见 calibration.run_walk_forward_grid）。
    """
    rows = []
    for label, ws, we in expanding_windows(start, end, step_days):
        bt = run_backtest(signals, weekly_df, settings, start=ws, end=we)
        port = portfolio_returns(bt)
        rows.append({"window": label, "window_start": ws, "window_end": we,
                     **evaluate(port["portfolio_return"],
                                turnover=port["avg_turnover"],
                                annual_periods=annual_periods)})
    return pd.DataFrame(rows)


# 兼容别名（旧名 run_walk_forward 已更名为 rolling_oos_evaluation）
run_walk_forward = rolling_oos_evaluation


def oos_summary(oos_df) -> dict:
    """OOS 汇总（26 号）：跨窗口汇总 OOS 绩效，判断优势是否持续。

    oos_df：rolling_oos_evaluation 输出（每行一个 OOS 窗口）。
    输出：
        n_windows / mean & median 的 Return/Sharpe/MDD / 正窗口占比 /
        hit_rate / turnover / 一致性判断（优势是否跨时间持续）。
    """
    if oos_df is None or len(oos_df) == 0:
        return {"n_windows": 0, "consistent": False}
    cols = {c: c for c in oos_df.columns}
    get = lambda c: oos_df[c].astype(float) if c in oos_df.columns \
        else None
    ret = get("annualized_return")
    sharpe = get("sharpe")
    mdd = get("max_drawdown")
    turn = get("avg_turnover") if "avg_turnover" in oos_df.columns \
        else get("turnover")
    hit = get("win_rate") if "win_rate" in oos_df.columns \
        else get("hit_rate")
    pos_windows = int((ret > 0).sum()) if ret is not None else 0
    med_sharpe = float(sharpe.median()) if sharpe is not None else None
    med_ret = float(ret.median()) if ret is not None else None
    med_mdd = float(mdd.median()) if mdd is not None else None
    # 一致性：正收益窗口占比 ≥ 60% 且中位 Sharpe > 0
    consistent = bool(
        ret is not None and pos_windows / len(oos_df) >= 0.6
        and (med_sharpe is None or med_sharpe > 0))
    return {
        "n_windows": int(len(oos_df)),
        "positive_windows": pos_windows,
        "positive_window_ratio": round(pos_windows / len(oos_df), 4),
        "mean_annualized_return": round(float(ret.mean()), 4)
        if ret is not None else None,
        "median_annualized_return": med_ret,
        "median_sharpe": med_sharpe,
        "median_max_drawdown": med_mdd,
        "median_turnover": round(float(turn.median()), 4)
        if turn is not None else None,
        "median_hit_rate": round(float(hit.median()), 4)
        if hit is not None else None,
        "consistent": consistent,
    }
