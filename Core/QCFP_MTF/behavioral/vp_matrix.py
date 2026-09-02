# coding: utf-8
"""量价结构矩阵（9 种 VP_Regime）

输入：月线价格方向（change_percent）+ 量/换手方向（volume_factors/turnover_factors）
"""

import pandas as pd


def _price_dir(change_percent, up_thr, down_thr):
    if pd.isna(change_percent):
        return None
    if change_percent > up_thr:
        return "↑"
    if change_percent < -down_thr:
        return "↓"
    return "→"


def build_vp_regime(m_df: pd.DataFrame, vol_factors: pd.DataFrame,
                    settings: dict) -> pd.DataFrame:
    cfg = settings.get("behavioral", {}).get("price_direction", {})
    up_thr = float(cfg.get("up_threshold", 1.5))
    down_thr = float(cfg.get("down_threshold", 1.5))

    price = m_df[["stock_code", "date", "change_percent"]].copy()
    price["month_end"] = pd.to_datetime(price["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    price["p_dir"] = price["change_percent"].map(lambda v: _price_dir(v, up_thr, down_thr))

    m = price[["stock_code", "month_end", "p_dir"]].merge(
        vol_factors[["stock_code", "month_end", "vol_dir", "turn_dir"]],
        on=["stock_code", "month_end"], how="left")

    def _vp(r):
        p, v, t = r["p_dir"], r["vol_dir"], r["turn_dir"]
        if None in (p, v, t):
            return None
        if p == "↑" and v == "↑↑" and t == "↑↑":
            return "VP_OVERHEAT"
        if p == "↓" and v == "↑↑" and t == "↑↑":
            return "VP_PANIC"
        if p == "↑" and v == "↑" and t == "↑":
            return "VP_EXPANSION"
        if p == "↑" and v == "→" and t == "→":
            return "VP_STABLE_ASCENT"
        if p == "↑" and v == "↓" and t == "↓":
            return "VP_LOCKED_CANDIDATE"
        if p == "→" and v == "↓" and t == "↓":
            return "VP_SHRINK"
        if p == "→" and v == "↑" and t == "↑":
            return "VP_DIVERGENCE_HIGH"
        if p == "↓" and v == "↓" and t == "↓":
            return "VP_DECLINE_SILENT"
        if p == "↓" and v == "↑" and t == "↑":
            return "VP_SELLING_ACTIVE"
        return "VP_NEUTRAL"

    m["m_vp_regime"] = m.apply(_vp, axis=1)
    return m[["stock_code", "month_end", "m_vp_regime"]].reset_index(drop=True)
