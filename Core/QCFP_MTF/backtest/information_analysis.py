# coding: utf-8
"""信息量分析（Layer 1 因子 / Layer 2 状态验证）

- forward_returns：前向 4/13/26 周收益
- factor_rank_ic：因子每周横截面 Spearman Rank IC
- state_forward_table：状态前向收益分层（均值/中位数/命中率）
"""

import numpy as np
import pandas as pd


def newey_west_se(values, lag: int) -> float:
    """Newey-West HAC 标准误（校正重叠样本自相关）"""
    x = np.asarray(values, dtype=float)
    x = x - x.mean()
    n = len(x)
    if n < 2:
        return np.nan
    lag = max(0, min(int(lag), n - 1))
    gamma = np.array([np.dot(x[: n - k], x[k:]) / n for k in range(lag + 1)])
    w = 1.0 - np.arange(lag + 1) / (lag + 1)
    var = gamma[0] + 2.0 * np.sum(w[1:] * gamma[1:])
    return float(np.sqrt(max(var, 0.0) / n))


def block_bootstrap_ci(values, block: int = 26, n_boot: int = 200,
                       alpha: float = 0.05, seed: int = 42):
    """块自助法 95% 置信区间（block=前向周数，保留重叠结构）"""
    x = np.asarray(values, dtype=float)
    n = len(x)
    if n < 2:
        return np.nan, np.nan
    rng = np.random.default_rng(seed)
    block = max(1, min(int(block), n))
    nblocks = int(np.ceil(n / block))
    means = []
    for _ in range(n_boot):
        starts = rng.integers(0, n - block + 1, size=nblocks) if n >= block \
            else rng.integers(0, n, size=nblocks)
        idx = np.concatenate([np.arange(s, min(s + block, n)) for s in starts])[:n]
        means.append(x[idx].mean())
    lo, hi = np.percentile(means, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(lo), float(hi)


def forward_returns(weekly_df, horizons=(4, 13, 26)) -> pd.DataFrame:
    df = weekly_df[["stock_code", "date", "close"]].copy()
    df["week_end"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df = df.sort_values(["stock_code", "week_end"])
    for h in horizons:
        df[f"fwd_{h}w"] = df.groupby("stock_code")["close"].shift(-h) / df["close"] - 1.0
    cols = ["stock_code", "week_end"] + [f"fwd_{h}w" for h in horizons]
    return df[cols].reset_index(drop=True)


def factor_rank_ic(panel, factor_col, fwd_col, date_col="week_end",
                   min_n=5) -> pd.DataFrame:
    """每周横截面 Spearman IC"""
    rows = []
    for d, g in panel.groupby(date_col):
        sub = g[[factor_col, fwd_col]].dropna()
        if len(sub) < min_n:
            continue
        # Spearman = 秩转 Pearson（避免 scipy 依赖）
        rank_f = sub[factor_col].rank()
        rank_r = sub[fwd_col].rank()
        rows.append({"date": d, "ic": rank_f.corr(rank_r)})
    return pd.DataFrame(rows, columns=["date", "ic"])


def ic_summary(ic_series: pd.Series) -> dict:
    ic = ic_series.dropna()
    if ic.empty:
        return {"n": 0, "mean_ic": np.nan, "std_ic": np.nan,
                "icir": np.nan, "positive_ratio": np.nan}
    mean = ic.mean()
    std = ic.std(ddof=0)
    return {
        "n": int(len(ic)),
        "mean_ic": round(float(mean), 4),
        "std_ic": round(float(std), 4),
        "icir": round(float(mean / std), 4) if std and std > 0 else None,
        "positive_ratio": round(float((ic > 0).mean()), 4),
    }


def state_forward_table(panel, state_col, fwd_col) -> pd.DataFrame:
    sub = panel[[state_col, fwd_col]].dropna()
    if sub.empty:
        return pd.DataFrame()
    g = sub.groupby(state_col)[fwd_col]
    rows = []
    for state, s in g:
        rows.append({
            state_col: state,
            "n": int(len(s)),
            "mean_fwd": round(float(s.mean()), 6),
            "median_fwd": round(float(s.median()), 6),
            "hit_rate": round(float((s > 0).mean()), 4),
        })
    out = pd.DataFrame(rows).set_index(state_col)
    return out.sort_values("mean_fwd", ascending=False)


def cfp_return_matrix(panel, horizons=(4, 13, 26)) -> pd.DataFrame:
    """C×F×P 三维组合前向收益矩阵

    输出每组合的 n / 均值 / 中位数 / 命中率 / t 值，用于验证三维框架的单调分层。
    """
    rows = []
    for h in horizons:
        fwd = f"fwd_{h}w"
        sub = panel[["c_state", "f_state", "p_state", "week_end", fwd]].dropna()
        if sub.empty:
            continue
        sub = sub.sort_values("week_end")
        g = sub.groupby(["c_state", "f_state", "p_state"])
        for (c, f, p), grp in g:
            s = grp[fwd]
            mean = s.mean()
            std = s.std(ddof=0)
            t_stat = float(mean / (std / np.sqrt(len(s)))) if std and std > 0 else None
            q10, q25, q75, q90 = s.quantile([0.10, 0.25, 0.75, 0.90])
            # 非重叠采样 t 统计（每 horizon 周取一个，校正重叠样本标准误）
            ns = grp.iloc[::h][fwd]
            ns_std = ns.std(ddof=0)
            t_ns = float(ns.mean() / (ns_std / np.sqrt(len(ns)))) \
                if ns_std and ns_std > 0 and len(ns) > 1 else None
            # Newey-West HAC t 与块自助法 CI（重叠样本专用）
            se_hac = newey_west_se(s.values, lag=max(h - 1, 1))
            t_hac = float(mean / se_hac) if se_hac and se_hac > 0 else None
            ci_lo, ci_hi = block_bootstrap_ci(s.values, block=h)
            rows.append({
                "c_state": c, "f_state": f, "p_state": p,
                "horizon": f"fwd_{h}w",
                "n": int(len(s)),
                "mean_fwd": round(float(mean), 6),
                "median_fwd": round(float(s.median()), 6),
                "hit_rate": round(float((s > 0).mean()), 4),
                "t_stat": round(t_stat, 3) if t_stat is not None else None,
                "t_stat_nonoverlap": round(t_ns, 3) if t_ns is not None else None,
                "t_stat_hac": round(t_hac, 3) if t_hac is not None else None,
                "ci_lo": round(ci_lo, 6) if ci_lo == ci_lo else None,
                "ci_hi": round(ci_hi, 6) if ci_hi == ci_hi else None,
                "std_fwd": round(float(std), 6) if std == std else None,
                "q10": round(float(q10), 6), "q25": round(float(q25), 6),
                "q75": round(float(q75), 6), "q90": round(float(q90), 6),
            })
    return pd.DataFrame(rows)


def conditional_regression(panel, fwd_col, score_cols=("c_s", "f_s", "p_s"),
                           min_n=5) -> dict:
    """每周横截面 OLS：FwdReturn ~ C + F + P（标准化）

    回答"C/F 在控制 P 后是否仍有独立增量解释力"：
    - mean_beta / t：各因子平均横截面回归系数
    - incremental_r2：完整模型相对仅 P 模型的 R² 增量
    """
    cols = list(score_cols)
    betas = {c: [] for c in cols}
    r2_full, r2_p = [], []
    for _, g in panel.groupby("week_end"):
        sub = g[cols + [fwd_col]].dropna()
        if len(sub) < min_n:
            continue
        y = sub[fwd_col].values.astype(float)
        X = sub[cols].values.astype(float)
        mu, sd = X.mean(0), X.std(0)
        sd = np.where(sd == 0, 1.0, sd)
        Xs = (X - mu) / sd
        X1 = np.column_stack([np.ones(len(sub)), Xs])
        b, *_ = np.linalg.lstsq(X1, y, rcond=None)
        yhat = X1 @ b
        ss_tot = np.sum((y - y.mean()) ** 2)
        r2_full.append(1 - np.sum((y - yhat) ** 2) / ss_tot if ss_tot else np.nan)
        xp = (sub["p_s"].values - sub["p_s"].mean())
        xp_sd = xp.std()
        if xp_sd and xp_sd > 0:
            Xp = np.column_stack([np.ones(len(sub)), xp / xp_sd])
            bp, *_ = np.linalg.lstsq(Xp, y, rcond=None)
            yhatp = Xp @ bp
            r2_p.append(1 - np.sum((y - yhatp) ** 2) / ss_tot if ss_tot else np.nan)
        else:
            r2_p.append(np.nan)
        for i, c in enumerate(cols):
            betas[c].append(float(b[i + 1]))
    out = {}
    for c, vals in betas.items():
        arr = np.asarray(vals, dtype=float)
        mean = arr.mean()
        std = arr.std(ddof=0)
        # Fama-MacBeth 风格：对 beta 时间序列做 Newey-West HAC 标准误
        se_hac = newey_west_se(arr, lag=min(4, len(arr) - 1))
        out[c] = {
            "mean_beta": round(float(mean), 6),
            "t": round(float(mean / (std / np.sqrt(len(arr)))), 3)
            if std and std > 0 else None,
            "t_hac": round(float(mean / se_hac), 3)
            if se_hac and se_hac > 0 and se_hac == se_hac else None,
            "n": int(len(arr)),
        }
    f = np.asarray([x for x in r2_full if x == x])
    p = np.asarray([x for x in r2_p if x == x])
    out["r2_full"] = round(float(f.mean()), 6) if len(f) else None
    out["r2_p_only"] = round(float(p.mean()), 6) if len(p) else None
    out["incremental_r2"] = round(float(f.mean() - p.mean()), 6) \
        if len(f) and len(p) else None
    return out
