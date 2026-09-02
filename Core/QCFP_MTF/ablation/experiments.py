# coding: utf-8
"""Ablation 实验协议（QCFP-MTF 2.7）

permutation_ablation：打乱某模块输入（如 Permission），验证其真实信息贡献；
time_shift_leakage：把决策日平移 +1 周（t+1 提前执行），检测时间错位/泄漏
（泄漏检测实验，禁止用于正式回测）。

Convergence（新 9A 号）：Legacy permutation ablation 退役为
RESEARCH_ARCHIVE / NON_CERTIFIABLE——正式 Certification 只认可
Paired time-series ablation + Block-aware inference + Bootstrap/sign-flip
+ Regime breakdown + Effect size。
"""

import random

import pandas as pd

from ..backtest.engine import portfolio_returns, run_backtest
from ..backtest.performance import evaluate as evaluate_perf
from ..decision.engine import DecisionConfig


def _perf(signals, weekly_kl, settings, start=None):
    bt = run_backtest(signals, weekly_kl, settings, start=start)
    port = portfolio_returns(bt)
    return evaluate_perf(port["portfolio_return"],
                         turnover=port["avg_turnover"])


def permutation_ablation(signals, weekly_kl, settings, daily=None,
                         seed=42, n_perm=5) -> dict:
    """打乱 Permission 输入（RESEARCH_ARCHIVE / NON_CERTIFIABLE）。"""
    from ..backtest.canonical import canonical_replay
    base = canonical_replay(signals, settings, run_id="perm_base", daily=daily)
    base_perf = _perf(base, weekly_kl, settings)
    rng = random.Random(seed)
    perms = ["BLOCK", "WATCH", "TEST", "ALLOW", "STRONG_ALLOW"]
    permuted_perfs = []
    permuted_returns = []
    for k in range(n_perm):
        codes = sorted(base["stock_code"].unique())
        shuffle_map = {c: rng.choice(perms) for c in codes}
        df = base.copy()
        targets = []
        prev_state, prev_pos = {}, {}
        for _, r in df.sort_values(
                ["stock_code", "decision_date"]).iterrows():
            cfg = DecisionConfig(override_permission=shuffle_map[r["stock_code"]])
            from ..decision.engine import evaluate
            snap = evaluate(dict(r), prev_state.get(r["stock_code"], "FLAT"),
                            prev_pos.get(r["stock_code"], 0.0), settings,
                            config=cfg)
            prev_state[r["stock_code"]] = snap.next_fsm_state
            prev_pos[r["stock_code"]] = snap.target_position
            targets.append(snap.target_position)
        df["target"] = targets
        p = _perf(df, weekly_kl, settings)
        permuted_perfs.append(p)
        permuted_returns.append(float(p.get("annualized_return") or 0.0))
    import numpy as np
    arr = np.array(permuted_returns)
    base_ret = float(base_perf.get("annualized_return") or 0.0)
    ci_low, ci_high = (float(np.percentile(arr, 2.5)),
                       float(np.percentile(arr, 97.5))) if len(arr) else (None, None)
    std = float(arr.std()) if len(arr) > 1 else 0.0
    return {
        "baseline": {"annualized_return": base_perf.get("annualized_return"),
                     "max_drawdown": base_perf.get("max_drawdown")},
        "permuted": [{"annualized_return": p.get("annualized_return"),
                      "max_drawdown": p.get("max_drawdown")}
                     for p in permuted_perfs],
        "n_perm": n_perm, "seed": seed,
        "incremental": {
            "delta_mean": round(base_ret - float(arr.mean()), 6)
            if len(arr) else None,
            "ci_low": round(ci_low, 6) if ci_low is not None else None,
            "ci_high": round(ci_high, 6) if ci_high is not None else None,
            "effect_size": round(base_ret / std, 4) if std > 0 else None,
        },
    }


def time_shift_leakage(signals, weekly_kl, settings, daily=None,
                       shift_weeks=1) -> dict:
    """把决策日平移 +1 周（信号提前生效）→ 与基线对比（泄漏检测）"""
    from ..backtest.canonical import canonical_replay
    base = canonical_replay(signals, settings, run_id="ts_base", daily=daily)
    base_perf = _perf(base, weekly_kl, settings)
    df = base.copy()
    df["decision_date"] = (
        pd.to_datetime(df["decision_date"]) - pd.Timedelta(weeks=shift_weeks)
    ).dt.strftime("%Y-%m-%d")
    shifted_perf = _perf(df, weekly_kl, settings)
    return {
        "baseline_annualized": base_perf.get("annualized_return"),
        "shifted_annualized": shifted_perf.get("annualized_return"),
        "leakage_suspect": bool(
            shifted_perf.get("annualized_return") is not None
            and base_perf.get("annualized_return") is not None
            and shifted_perf.get("annualized_return")
            > base_perf.get("annualized_return") * 1.2),
        "shift_weeks": shift_weeks,
    }
