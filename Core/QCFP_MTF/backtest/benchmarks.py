# coding: utf-8
"""Benchmark / Counterfactual 基准体系（QCFP-MTF 2.7）

回答"QCFP_MTF 是否真的比简单方法更有价值"：
    B0 Buy&Hold / B1 Market Index / B2 Simple Trend / B3 Breakout /
    B4 Wave Only / B5 Permission Only / B6 Permission + Wave / B7 Full
比较 Return / MDD / Sharpe / Calmar / Wave Capture / False Entry /
Turnover / Capital Efficiency + 风险调整增量效用。
"""

import numpy as np
import pandas as pd

from ..decision.institutional_permission import evaluate_institutional_permission
from ..wave.signal import evaluate_wave_signal


def _permission_target(row, settings):
    inst = evaluate_institutional_permission(
        c_state=row.get("c_state"), f_state=row.get("f_state"),
        p_state=row.get("p_state"),
        persistence=2 if row.get("f_state") == "F↑"
        and row.get("prev_f_state") == "F↑" else 1 if row.get("f_state") == "F↑"
        else 0,
        confidence=row.get("chip_stability_confidence") or "Medium",
        data_quality=row.get("data_quality") or "B", settings=settings)
    return {"BLOCK": 0.0, "WATCH": 0.0, "TEST": 0.2,
            "ALLOW": 0.5, "STRONG_ALLOW": 0.7}.get(inst.permission, 0.0)


def benchmark_targets(signals: pd.DataFrame, weekly_kl: pd.DataFrame,
                      settings) -> dict:
    """B0–B7 各基准的 target 序列（as-of，无未来信息）"""
    out = {}
    # B0 Buy&Hold
    s0 = signals.copy(); s0["target"] = 1.0
    out["B0_BuyHold"] = s0
    # B2 Simple Trend（close > 20 周 MA）
    w = weekly_kl.copy()
    w["week_end"] = pd.to_datetime(w["date"]).dt.strftime("%Y-%m-%d")
    w = w.sort_values(["stock_code", "week_end"])
    w["ma20"] = w.groupby("stock_code")["close"].transform(
        lambda x: x.rolling(20, min_periods=5).mean())
    w["trend"] = (w["close"] > w["ma20"]).astype(float)
    s2 = signals.merge(w[["stock_code", "week_end", "trend"]],
                       left_on=["stock_code", "decision_date"],
                       right_on=["stock_code", "week_end"], how="left")
    s2["target"] = s2["trend"].fillna(0.0)
    out["B2_SimpleTrend"] = s2.drop(
        columns=[c for c in ("week_end", "trend") if c in s2.columns])
    # B3 Breakout（周涨幅 > 5%）
    w["ret"] = w.groupby("stock_code")["close"].pct_change()
    w["breakout"] = (w["ret"] > 0.05).astype(float)
    s3 = signals.merge(w[["stock_code", "week_end", "breakout"]],
                       left_on=["stock_code", "decision_date"],
                       right_on=["stock_code", "week_end"], how="left")
    s3["target"] = s3["breakout"].fillna(0.0)
    out["B3_Breakout"] = s3.drop(
        columns=[c for c in ("week_end", "breakout") if c in s3.columns])
    # B4 Wave Only（as-of wave_signal：strength≥0.4 且 UP）
    w["wave_ok"] = w.groupby("stock_code")["close"].transform(
        lambda x: x.rolling(13, min_periods=4).apply(
            lambda y: 1.0 if (evaluate_wave_signal(list(y)).direction == "UP"
                              and evaluate_wave_signal(list(y)).strength >= 0.4)
            else 0.0))
    s4 = signals.merge(w[["stock_code", "week_end", "wave_ok"]],
                       left_on=["stock_code", "decision_date"],
                       right_on=["stock_code", "week_end"], how="left")
    s4["target"] = s4["wave_ok"].fillna(0.0)
    out["B4_WaveOnly"] = s4.drop(
        columns=[c for c in ("week_end", "wave_ok") if c in s4.columns])
    # B5 Permission Only
    s5 = signals.copy()
    s5["target"] = [_permission_target(r, settings) for _, r in s5.iterrows()]
    out["B5_PermissionOnly"] = s5
    # B6 Permission + Wave
    s6 = s5.merge(w[["stock_code", "week_end", "wave_ok"]],
                  left_on=["stock_code", "decision_date"],
                  right_on=["stock_code", "week_end"], how="left")
    s6["target"] = s6["target"] * s6["wave_ok"].fillna(0.0)
    out["B6_PermissionWave"] = s6.drop(
        columns=[c for c in ("week_end", "wave_ok") if c in s6.columns])
    # B7 Full：由 canonical_replay 提供（调用方传入）
    return out


def risk_adjusted_incremental(base, candidate, mdd_base=None,
                              mdd_cand=None) -> float:
    """增量效用 = ΔReturn / Δ风险占用（MDD 差），避免"收益↑但风险↑↑"误判"""
    if base is None or candidate is None:
        return None
    ret_d = float(candidate) - float(base)
    risk_d = abs(float(mdd_cand or 0.0)) - abs(float(mdd_base or 0.0))
    if risk_d <= 0:
        return round(ret_d, 6) if ret_d != 0 else 0.0
    return round(ret_d / risk_d, 6)
