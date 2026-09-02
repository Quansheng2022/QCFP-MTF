# coding: utf-8
"""Portfolio-level Exposure Constraints（QCFP-MTF 2.5）

target 是"单股票目标暴露"，不是组合权重；组合层必须有最终 cap：
    单股 ≤ max_single_stock（默认 30%）
    行业 ≤ max_sector（默认 50%）
    每周总暴露 ≤ max_total_exposure（默认 100%）

约束在 target 层生效（T+1 前），避免 10 只 × 30% = 300% gross exposure。
"""

import pandas as pd


def apply_target_constraints(signals: pd.DataFrame, settings,
                             sector_map=None) -> pd.DataFrame:
    cfg = (settings or {}).get("backtest", {}).get(
        "portfolio_constraints", {})
    if not cfg.get("enabled", False):
        return signals
    out = signals.copy()
    max_single = float(cfg.get("max_single_stock", 0.30))
    max_sector = float(cfg.get("max_sector", 0.50))
    max_total = float(cfg.get("max_total_exposure", 1.0))
    if "target" not in out.columns:
        return out
    # ① 单股上限
    out["target"] = out["target"].clip(upper=max_single)
    # ② 行业上限（sector_map: stock_code → sector）
    if sector_map and max_sector < 1.0:
        out["_sector"] = out["stock_code"].map(sector_map).fillna("UNKNOWN")
        for _, g in out.groupby(["decision_date", "_sector"]):
            s = float(g["target"].sum())
            if s > max_sector and s > 0:
                out.loc[g.index, "target"] *= max_sector / s
    # ③ 每周总暴露上限
    for _, g in out.groupby("decision_date"):
        s = float(g["target"].sum())
        if s > max_total and s > 0:
            out.loc[g.index, "target"] *= max_total / s
    out = out.drop(columns=["_sector"]) if "_sector" in out.columns else out
    return out


def apply_portfolio_governance(signals: pd.DataFrame, settings,
                               sector_map=None) -> pd.DataFrame:
    """组合级治理（2.7）：单股/行业/总暴露 + 现金储备 + 总风险预算 + 高相关上限"""
    cfg = (settings or {}).get("backtest", {}).get(
        "portfolio_constraints", {})
    if not cfg.get("enabled", False):
        return signals
    from ..decision.stop_loss import stop_loss_buffer_pct
    out = apply_target_constraints(signals, settings, sector_map)
    # 现金储备：总暴露 ≤ 1 - min_cash
    min_cash = float(cfg.get("min_cash", 0.0))
    total_cap = 1.0 - min_cash
    for _, g in out.groupby("decision_date"):
        s = float(g["target"].sum())
        if s > total_cap and s > 0:
            out.loc[g.index, "target"] *= total_cap / s
    # 总风险预算：Σ(仓位 × 止损距离) ≤ total_risk_budget
    stop = stop_loss_buffer_pct(settings)
    trb = float(cfg.get("total_risk_budget", 0.06))
    for _, g in out.groupby("decision_date"):
        risk = float((g["target"] * stop).sum())
        if risk > trb and risk > 0:
            out.loc[g.index, "target"] *= trb / risk
    # 高相关组合上限（行业代理）
    hc = float(cfg.get("high_corr_cap", 0.30))
    if sector_map and hc < 1.0:
        out["_sector"] = out["stock_code"].map(sector_map).fillna("UNKNOWN")
        for _, g in out.groupby(["decision_date", "_sector"]):
            s = float(g["target"].sum())
            if s > hc and s > 0:
                out.loc[g.index, "target"] *= hc / s
        out = out.drop(columns=["_sector"])
    return out
