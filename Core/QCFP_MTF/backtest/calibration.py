# coding: utf-8
"""参数校准：网格搜索（Sharpe 优先）

候选参数作用于决策/回测层（Chip 权重、REDUCE 仓位），
不需要重跑 P1~P3 因子引擎，由 data_pipeline 即时重算。
"""

import json

import pandas as pd

from ..config.settings import _deep_merge
from .cross_validation import walk_forward_windows
from .data_pipeline import build_signal_timeline
from .engine import portfolio_returns, run_backtest
from .lookahead_filter import assert_no_lookahead
from .performance import evaluate


def run_grid(structural, monthly, weekly, chip, idx_df, weekly_kl,
             settings, grid, start=None, end=None, annual_periods=52,
             stocks_filter=None, daily=None) -> pd.DataFrame:
    """对参数网格逐组合回测，返回按 Sharpe 降序的结果表"""
    rows = []
    for combo in grid:
        s = _deep_merge(settings, combo)
        try:
            signals = build_signal_timeline(structural, monthly, weekly, chip,
                                            idx_df, s, stocks=stocks_filter,
                                            weekly_kl=weekly_kl, daily=daily)
            assert_no_lookahead(signals)
            bt = run_backtest(signals, weekly_kl, s, start=start, end=end)
            port = portfolio_returns(bt)
            perf = evaluate(port["portfolio_return"], turnover=port["avg_turnover"],
                            annual_periods=annual_periods)
            rows.append({**combo, **perf})
        except Exception as e:  # noqa: BLE001
            rows.append({**combo, "error": str(e)})
    df = pd.DataFrame(rows)
    if "sharpe" in df.columns:
        df = df.sort_values("sharpe", ascending=False, na_position="last")
        best = df["sharpe"].max()
        tol = max(0.01, abs(best) * 0.1)
        plateau = df[df["sharpe"] >= best - tol]
        df.attrs["plateau"] = {
            "best_sharpe": float(best),
            "tol": float(tol),
            "n_plateau": int(len(plateau)),
            "total": int(len(df)),
            "plateau_params": plateau[["fusion", "backtest", "sharpe"]]
            .to_dict(orient="records"),
        }
    return df.reset_index(drop=True)


def run_walk_forward_grid(structural, monthly, weekly, chip, idx_df, weekly_kl,
                          settings, grid, start, end, train_years=2, test_years=1,
                          annual_periods=52, stocks_filter=None,
                          daily=None) -> pd.DataFrame:
    """Walk-forward OOS 校准：训练窗选参 → 测试窗独立评估（只看 OOS）"""
    rows = []
    for label, tr_s, tr_e, te_s, te_e in walk_forward_windows(
            start, end, train_years, test_years):
        train_res = run_grid(structural, monthly, weekly, chip, idx_df, weekly_kl,
                             settings, grid, start=tr_s, end=tr_e,
                             annual_periods=annual_periods,
                             stocks_filter=stocks_filter, daily=daily)
        if train_res.empty:
            continue
        best = train_res.iloc[0]
        combo = {}
        for key in ("fusion", "backtest"):
            if isinstance(best.get(key), dict):
                combo[key] = best[key]
        s = _deep_merge(settings, combo) if combo else settings
        signals = build_signal_timeline(structural, monthly, weekly, chip,
                                        idx_df, s, stocks=stocks_filter,
                                        weekly_kl=weekly_kl, daily=daily)
        bt = run_backtest(signals, weekly_kl, s, start=te_s, end=te_e)
        port = portfolio_returns(bt)
        oos = evaluate(port["portfolio_return"], turnover=port["avg_turnover"],
                       annual_periods=annual_periods)
        rows.append({"window": label, "train_end": tr_e,
                     "test_start": te_s, "test_end": te_e,
                     "train_sharpe": best.get("sharpe"),
                     "train_return": best.get("annualized_return"),
                     "train_mdd": best.get("max_drawdown"),
                     "best_params": json.dumps(combo, ensure_ascii=False) if combo else None,
                     **oos})
    out = pd.DataFrame(rows)
    if not out.empty and out["best_params"].notna().any():
        mode = out["best_params"].mode().iloc[0]
        out.attrs["param_stability"] = {
            "n_windows": int(len(out)),
            "stable_windows": int((out["best_params"] == mode).sum()),
            "mode_params": mode,
        }
    return out
