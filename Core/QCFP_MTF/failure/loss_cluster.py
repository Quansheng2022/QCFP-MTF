# coding: utf-8
"""Loss Cluster Detector（QCFP-MTF 2.8：45 号连续错误交易检测）

单笔亏损不一定有问题，连续亏损 + 同一 Regime + MFE 持续下降
→ 说明"不是偶然，而是当前方法可能已不适应市场"：
    Strategy Confidence ↓ / Risk Budget ↓

计算：
    Consecutive Losses / Rolling Hit Rate / Rolling MFE / Rolling MAE /
    False Entry Rate / Regime
"""

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class LossCluster:
    consecutive_losses: int
    rolling_hit_rate: float
    rolling_mfe_mean: float
    rolling_mae_mean: float
    false_entry_rate: float
    regime: str
    cluster_triggered: bool
    strategy_confidence_scale: float
    risk_budget_scale: float
    reasons: tuple = field(default_factory=tuple)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["reasons"] = list(self.reasons)
        return d


def detect_loss_cluster(trades, regime="Sideway", window=10,
                        consecutive_threshold=3, hit_rate_threshold=0.35,
                        mfe_decline_threshold=0.5,
                        false_entry_threshold=0.4) -> LossCluster:
    """连续错误检测。

    trades：按时间排序的逐笔交易 [{net_return, mfe, mae, false_entry}]
    触发条件（满足任一）：
        A. 连续亏损 ≥ consecutive_threshold
        B. 滚动胜率 < hit_rate_threshold 且 滚动 MFE 下降
        C. 滚动 MFE 低于前窗 50% 且 假进场率 ≥ 阈值（同一 regime）
    """
    w = trades[-window:] if len(trades) >= window else trades
    n = len(w)
    consec = 0
    for t in reversed(trades):
        if float(t.get("net_return") or 0.0) < 0:
            consec += 1
        else:
            break
    wins = [1 if float(t.get("net_return") or 0.0) > 0 else 0 for t in w]
    hit = sum(wins) / n if n else 0.0
    mfe = [float(t.get("mfe") or 0.0) for t in w]
    mae = [float(t.get("mae") or 0.0) for t in w]
    mfe_mean = sum(mfe) / len(mfe) if mfe else 0.0
    mae_mean = sum(mae) / len(mae) if mae else 0.0
    false_entry = sum(1 for t in w if t.get("false_entry")) / n if n else 0.0
    # 前窗 MFE（更早的交易）
    prev_w = trades[-2 * window:-window] if len(trades) >= 2 * window else []
    prev_mfe = sum(float(t.get("mfe") or 0.0) for t in prev_w) / \
        len(prev_w) if prev_w else None
    mfe_declining = prev_mfe is not None and mfe_mean < \
        prev_mfe * mfe_decline_threshold
    reasons = []
    triggered = False
    if consec >= consecutive_threshold:
        triggered = True
        reasons.append(f"CONSECUTIVE_LOSSES_{consec}")
    if hit < hit_rate_threshold and mfe_declining:
        triggered = True
        reasons.append(f"LOW_HIT_RATE({hit:.0%})_MFE_DECLINING")
    if mfe_declining and false_entry >= false_entry_threshold:
        triggered = True
        reasons.append(f"FALSE_ENTRY({false_entry:.0%})_MFE_DECLINING")
    if triggered:
        reasons.append(f"REGIME={regime}")
    conf_scale = 0.6 if triggered else 1.0
    budget_scale = 0.5 if triggered else 1.0
    if consec >= consecutive_threshold + 2:
        conf_scale = min(conf_scale, 0.4)
        budget_scale = min(budget_scale, 0.3)
    return LossCluster(
        consecutive_losses=consec,
        rolling_hit_rate=round(hit, 4),
        rolling_mfe_mean=round(mfe_mean, 4),
        rolling_mae_mean=round(mae_mean, 4),
        false_entry_rate=round(false_entry, 4),
        regime=regime,
        cluster_triggered=triggered,
        strategy_confidence_scale=round(conf_scale, 4),
        risk_budget_scale=round(budget_scale, 4),
        reasons=tuple(reasons))
