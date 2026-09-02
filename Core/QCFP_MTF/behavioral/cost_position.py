# coding: utf-8
"""Cost Position（成本位置）—— CBI 剥离后的独立模块

VWAP = 周期 amount/volume；比较月末 close 与周/月/季 VWAP 判断多周期成本优劣。
"""

import pandas as pd


def _clean_vwap(s: pd.Series) -> pd.Series:
    s = s.copy()
    s = s.where(s.notna() & (s > 0))
    return s


def build_cost_position(m_df: pd.DataFrame, w_df: pd.DataFrame, q_df: pd.DataFrame,
                        settings: dict) -> pd.DataFrame:
    neutral_pct = float(settings.get("behavioral", {})
                        .get("cost_position", {}).get("neutral_pct", 2.0))

    m = m_df[["stock_code", "stock_name", "date", "close", "amount", "volume"]].copy()
    m["month_end"] = pd.to_datetime(m["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    m["vwap_m"] = _clean_vwap(m["amount"] / m["volume"].where(m["volume"] > 0))
    m = m.sort_values("date").reset_index(drop=True)

    w = w_df[["stock_code", "date", "amount", "volume"]].copy()
    w["vwap_w"] = _clean_vwap(w["amount"] / w["volume"].where(w["volume"] > 0))
    w = w[w["vwap_w"].notna()].sort_values("date")

    q = q_df[["stock_code", "date", "amount", "volume"]].copy()
    q["vwap_q"] = _clean_vwap(q["amount"] / q["volume"].where(q["volume"] > 0))
    q = q[q["vwap_q"].notna()].sort_values("date")

    # 最近一周 / 最近已披露季度 VWAP（backward 对齐）
    m = pd.merge_asof(m, w, on="date", by="stock_code", direction="backward")
    m = pd.merge_asof(m, q, on="date", by="stock_code", direction="backward",
                      suffixes=("_w", "_q"))

    m["cost_vs_weekly_vwap"] = m["close"] / m["vwap_w"] - 1.0
    m["cost_vs_monthly_vwap"] = m["close"] / m["vwap_m"] - 1.0
    m["cost_vs_quarterly_vwap"] = m["close"] / m["vwap_q"] - 1.0

    def _status(r):
        c, vm, vq = r["close"], r["vwap_m"], r["vwap_q"]
        if pd.isna(c) or pd.isna(vm) or pd.isna(vq):
            return None
        up = vm * (1 + neutral_pct / 100.0)
        low = vm * (1 - neutral_pct / 100.0)
        if c > up and c > vq:
            return "COST_ADVANTAGE"
        if c < low and c < vq:
            return "COST_DISADVANTAGE"
        return "COST_NEUTRAL"

    m["cost_position"] = m.apply(_status, axis=1)
    cols = ["stock_code", "stock_name", "month_end",
            "cost_position", "cost_vs_weekly_vwap",
            "cost_vs_monthly_vwap", "cost_vs_quarterly_vwap"]
    return m[cols].reset_index(drop=True)
