# coding: utf-8
"""Retail Utility（QCFP-MTF 2.5：牛散实战评价函数）

牛散评价的 6 个可量化指标：
    ① Wave Capture     捕获波段上涨的比例（capture_ratio）
    ② MAE              最大不利波动
    ③ MFE              最大有利波动
    ④ Opportunity Miss 因 WATCH/BLOCK/Cooldown 错过的大波段比例
    ⑤ False Participation 参与后亏损/低 MFE 的比例
    ⑥ Capital Efficiency 收益 / 平均资金占用

Retail Utility Score（评价用，不用于校准/优化）：
    40% Return + 20% Capital Efficiency + 15% Wave Capture +
    10% Profit Factor − 10% MaxDD − 5% Turnover
"""

import numpy as np
import pandas as pd


def capital_efficiency(annualized_return, avg_exposure) -> float:
    if avg_exposure and avg_exposure > 0 and annualized_return is not None:
        return float(annualized_return) / float(avg_exposure)
    return 0.0


def false_participation_rate(metrics: pd.DataFrame) -> float:
    """参与后策略收益 <= 0 的波段占比（NaN → Unknown，不计为亏损）"""
    if metrics is None or metrics.empty:
        return None
    part = metrics[metrics["participated"]
                   & metrics["strategy_return"].notna()]
    if part.empty:
        return None
    losing = part["strategy_return"] <= 0
    return round(float(losing.mean()), 4)


def risk_budget_efficiency(annualized_return, max_drawdown,
                           avg_exposure) -> float:
    """收益 / 最大风险占用（牛散视角：少占资金、少回撤的波段更有价值）"""
    risk_capital = abs(float(max_drawdown or 0.0)) * float(avg_exposure or 0.0)
    if risk_capital > 0 and annualized_return is not None:
        return round(float(annualized_return) / risk_capital, 6)
    return None


def opportunity_cost(metrics: pd.DataFrame) -> dict:
    """被 Permission/Cooldown/Risk 过滤（未参与）波段的平均少赚（机会成本）"""
    if metrics is None or metrics.empty:
        return {"n_missed": 0}
    missed = metrics[~metrics["participated"]]
    if missed.empty:
        return {"n_missed": 0}
    gains = missed["gain"]
    return {
        "n_missed": int(len(missed)),
        "mean_gain": round(float(gains.mean()), 4),
        "ge20pct": int((gains >= 0.20).sum()),
        "ge50pct": int((gains >= 0.50).sum()),
        "ge100pct": int((gains >= 1.0).sum()),
    }


def time_in_position(bt: pd.DataFrame) -> float:
    """持仓周占比（Time-in-Position）"""
    if bt is None or bt.empty:
        return 0.0
    return round(float((bt["position_start"] > 0).mean()), 4)


def false_exit_rate(bt: pd.DataFrame, weekly_kl: pd.DataFrame,
                    lookback: int = 4, gain_threshold: float = 0.05) -> float:
    """错误退出率：退出后 lookback 周内价格继续上涨 > 阈值 的比例"""
    w = weekly_kl.copy()
    w["week_end"] = pd.to_datetime(w["date"]).dt.strftime("%Y-%m-%d")
    w = w.sort_values(["stock_code", "week_end"]).reset_index(drop=True)
    w["fwd"] = w.groupby("stock_code")["close"].shift(-lookback) / \
        w["close"] - 1.0
    b = bt.copy()
    b["week_end"] = pd.to_datetime(b["week_end"]).dt.strftime("%Y-%m-%d")
    exits = b[(b["position_start"] > 0) & (b["position"] == 0)].copy()
    if exits.empty:
        return None
    m = exits.merge(w[["stock_code", "week_end", "fwd"]],
                    on=["stock_code", "week_end"], how="left")
    ok = m["fwd"].notna()
    if not ok.any():
        return None
    return round(float((m.loc[ok, "fwd"] > gain_threshold).mean()), 4)


def whipsaw_rate(bt: pd.DataFrame, lookback: int = 4) -> float:
    """波段噪声率：建仓后 lookback 周内即退出的建仓比例"""
    b = bt.sort_values(["stock_code", "week_end"]).reset_index(drop=True)
    b["prev_pos"] = b.groupby("stock_code")["position_start"].shift(1).fillna(0)
    entries = b[(b["position_start"] > 0) & (b["prev_pos"] == 0)].copy()
    if entries.empty:
        return None
    whipsaw = 0
    for _, e in entries.iterrows():
        seg = b[(b["stock_code"] == e["stock_code"])
                & (b.index > e.name)
                & (b.index <= e.name + lookback)]
        if (seg["position_start"] == 0).any():
            whipsaw += 1
    return round(whipsaw / len(entries), 4)


def retail_utility_score(annualized_return, avg_exposure, wave_capture_ratio,
                         profit_factor, max_drawdown, turnover) -> dict:
    """牛散评价函数（Evaluation Metric，非 Calibration Target）"""
    ret = float(annualized_return or 0.0)
    cap_eff = capital_efficiency(annualized_return, avg_exposure)
    wave = float(wave_capture_ratio or 0.0)
    pf = float(profit_factor or 0.0)
    mdd = float(max_drawdown or 0.0)
    to = float(turnover or 0.0)
    score = (0.40 * ret + 0.20 * cap_eff + 0.15 * wave
             + 0.10 * pf - 0.10 * abs(mdd) - 0.05 * to)
    return {
        "retail_utility_score": round(score, 6),
        "capital_efficiency": round(cap_eff, 6),
        "opportunity_miss_rate": None,   # 由 wave_summary.missed_wave_rate 填充
        "false_participation_rate": None,
        "weights": {"return": 0.40, "capital_efficiency": 0.20,
                    "wave_capture": 0.15, "profit_factor": 0.10,
                    "max_drawdown": -0.10, "turnover": -0.05},
    }


def holding_period_efficiency(net_return, holding_days, capital=1.0,
                              mfe=None, mae=None) -> dict:
    """持仓周期效率（64 号）：
        Holding Efficiency = Return / Capital / Time
    并输出 MFE/Holding Days、MAE/Holding Days、Return per Capital-Day。
    """
    ret = float(net_return or 0.0)
    days = max(1, int(holding_days or 0))
    cap = max(0.01, float(capital or 1.0))
    mfe = float(mfe or 0.0)
    mae = float(mae or 0.0)
    return {
        "return_per_capital_day": round(ret / cap / days, 6),
        "mfe_per_holding_day": round(mfe / days, 6),
        "mae_per_holding_day": round(mae / days, 6),
        "holding_efficiency": round(ret / cap / days, 6),
        "holding_days": days,
        "annualized_return": round((1 + ret) ** (365 / days) - 1, 4),
    }
