# coding: utf-8
"""Regime Transition Engine（QCFP-MTF 2.8：41 号市场状态转折引擎）

不要等市场已进入新状态才调整——在状态转换阶段主动降低脆弱性。
    Market Regime → Transition Detection → Transition Confidence → Risk Adjustment

2.8（41 号）强化：
    Transition Probability / Confidence / Speed / Persistence / Early Warning
    并直接输出阈值调整：Risk Budget ↓ / Entry Threshold ↑ / Add Threshold ↑ /
    Exit Sensitivity ↑（供决策/仓位层消费）。
"""

import numpy as np

from .regime import classify_regime


TRANSITION_RISK_SCALE = {
    ("Bull", "Bear"): 0.5,
    ("Bull", "Sideway"): 0.7,
    ("Sideway", "Bear"): 0.7,
    ("Bear", "Bull"): 0.8,
    ("Sideway", "Bull"): 1.0,
    ("Bear", "Sideway"): 1.0,
    ("HighVolatility", "Crisis"): 0.4,
    ("Crisis", "HighVolatility"): 0.6,
}


def detect_transitions(regime_series) -> list:
    """regime_series：[(date, regime)] → 转折事件列表"""
    out = []
    for i in range(1, len(regime_series)):
        prev_date, prev = regime_series[i - 1]
        cur_date, cur = regime_series[i]
        if cur != prev:
            # 置信度 = 新状态已持续周数（截至当前）
            j = i
            while j < len(regime_series) and regime_series[j][1] == cur:
                j += 1
            confidence = min(1.0, (j - i) / 3.0)
            out.append({"from": prev, "to": cur, "date": cur_date,
                        "confidence": round(confidence, 2)})
    return out


def transition_risk_adjustment(prev_regime, regime) -> float:
    """转折期风险调整系数（1.0 = 无调整，<1 = 降低新增仓位/缩短容忍度）"""
    return TRANSITION_RISK_SCALE.get((prev_regime, regime), 1.0)


def transition_probability(regime_series, window=4) -> float:
    """转折概率：近 window 个时点中发生状态变化的比例（0-1）。"""
    if len(regime_series) < 2:
        return 0.0
    w = regime_series[-window:] if len(regime_series) >= window \
        else regime_series
    flips = sum(1 for i in range(1, len(w)) if w[i][1] != w[i - 1][1])
    return round(flips / max(1, len(w) - 1), 4)


def transition_speed(regime_series, window=6) -> float:
    """转折速度：近 window 内状态变化次数（周/时点）。"""
    w = regime_series[-window:] if len(regime_series) >= window \
        else regime_series
    flips = sum(1 for i in range(1, len(w)) if w[i][1] != w[i - 1][1])
    return float(flips)


def regime_persistence(regime_series, current_regime=None) -> dict:
    """当前状态持久性：已持续时点数 + 与历史平均持续的比较。"""
    if not regime_series:
        return {"current_regime": "", "persisted_periods": 0, "pctl": None}
    cur = current_regime or regime_series[-1][1]
    n = 0
    for date, r in reversed(regime_series):
        if r == cur:
            n += 1
        else:
            break
    # 历史该状态的平均持续
    runs = []
    run = 0
    prev = None
    for _, r in regime_series:
        if r == cur and r == prev:
            run += 1
        elif r == cur:
            run = 1
        else:
            if run:
                runs.append(run)
            run = 0
        prev = r
    if run:
        runs.append(run)
    avg = sum(runs) / len(runs) if runs else 0
    return {"current_regime": cur, "persisted_periods": n,
            "avg_persistence": round(avg, 2) if avg else None,
            "pctl": round(n / avg, 2) if avg else None}


def early_warning(regime_series, warn_flip_rate=0.3,
                  warn_bad_regime=("Bear", "Crisis")) -> dict:
    """早期预警：转折概率高 / 速度加快 / 已进入不利状态且不稳定。"""
    prob = transition_probability(regime_series)
    speed = transition_speed(regime_series)
    pers = regime_persistence(regime_series)
    warnings = []
    if prob >= warn_flip_rate:
        warnings.append(f"TRANSITION_PROBABILITY_HIGH({prob:.0%})")
    if speed >= 3:
        warnings.append(f"TRANSITION_SPEED_HIGH({speed})")
    if pers["current_regime"] in warn_bad_regime and pers["pctl"] \
            and pers["pctl"] <= 1.0:
        warnings.append(f"UNSTABLE_{pers['current_regime']}"
                        f"(persist={pers['persisted_periods']})")
    return {"transition_probability": prob, "transition_speed": speed,
            "persistence": pers, "warnings": warnings,
            "early_warning": bool(warnings)}


def threshold_adjustments(prev_regime, regime, regime_series=None) -> dict:
    """转折期阈值调整（供决策层消费）：
        risk_budget_scale   风险预算缩放（<1 = 降低）
        entry_threshold_up   进场阈值上调（Wave/TQS 门槛 × 系数）
        add_threshold_up     加仓阈值上调
        exit_sensitivity_up  退出敏感度上调（止损/时间容忍度收紧）
    转折风险越高的组合，调整越激进；回归稳定状态 → 1.0。
    """
    base = transition_risk_adjustment(prev_regime, regime)
    ew = early_warning(regime_series) if regime_series else \
        {"warnings": [], "early_warning": False}
    w = 1.0
    if ew["early_warning"]:
        w = max(0.7, base)
    return {
        "risk_budget_scale": round(min(base, w), 4),
        "entry_threshold_up": round(1.0 + (1.0 - min(base, w)) * 0.5, 4),
        "add_threshold_up": round(1.0 + (1.0 - min(base, w)) * 0.6, 4),
        "exit_sensitivity_up": round(1.0 + (1.0 - min(base, w)) * 0.4, 4),
        "transition": {"from": prev_regime, "to": regime},
        "early_warning": ew,
    }


def regime_series_from_idx(idx_df, dates, lookback=60) -> list:
    """按日期序列输出 (date, regime)（as-of）"""
    out = []
    for d in dates:
        out.append((str(d), classify_regime(idx_df, d, lookback=lookback)))
    return out
