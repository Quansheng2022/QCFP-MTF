# coding: utf-8
"""日线时机门（L4 · Tactical Timing Gate）

Model B：在 Q/M/W 周线决策之上叠加日线时机。
只改变 target / action 的"时机"，不改变 Q/M/W 战略状态：
    - DAILY_BREAKOUT / DAILY_ACCUMULATION
                         → 允许早入场（WAIT 升级为 ENTER）＋战术加仓（HOLD/试多 ×1.25，不超 Risk 上限）
    - DAILY_DISTRIBUTION → 战术减仓（BUY/ADD/HOLD/试多 target × reduce_factor）
    - DAILY_PULLBACK     → 不回撤不减仓（持有）
PIT：日线状态按 trade_date <= 决策日 as-of 对齐。
"""

import pandas as pd

from ..decision.position_sizing import effective_position, risk_cap

# 允许"日线突破→早入场"的战略状态（战略上允许、但周线尚未确认）
EARLY_ENTRY_STATES = {"BEARISH_RECOVERY_CANDIDATE", "BULLISH_WARNING"}
# 日线看多触发：突破（确认启动）＋吸筹（潜在突破）
TACTICAL_BULLISH = {"DAILY_BREAKOUT", "DAILY_ACCUMULATION"}


def apply_daily_timing_gate(signals: pd.DataFrame, daily: pd.DataFrame,
                            settings: dict) -> pd.DataFrame:
    """返回加了日线时机的信号副本（target 修改 + timing_action 标注）"""
    if not settings.get("daily", {}).get("timing", {}).get("enabled", False):
        out = signals.copy()
        out["timing_action"] = out["action_signal"]
        return out
    if daily is None or daily.empty:
        out = signals.copy()
        out["timing_action"] = out["action_signal"]
        return out
    cfg = settings.get("daily", {}).get("timing", {})
    reduce_factor = float(cfg.get("distribution_reduce", 0.5))
    add_ratio = float(cfg.get("breakout_add_ratio", 1.25))

    d = daily[["stock_code", "trade_date", "daily_state"]].copy()
    d["daily_date_dt"] = pd.to_datetime(d["trade_date"], errors="coerce")
    d = d.dropna(subset=["daily_date_dt"]).sort_values("daily_date_dt")

    out = signals.copy()
    out["decision_dt"] = pd.to_datetime(out["decision_date"], errors="coerce")
    out = out.sort_values("decision_dt")
    joined = pd.merge_asof(
        out, d, left_on="decision_dt", right_on="daily_date_dt",
        by="stock_code", direction="backward")
    joined["timing_action"] = joined["action_signal"]
    joined["_target"] = joined["target"].astype(float)

    dist = joined["daily_state"] == "DAILY_DISTRIBUTION"
    joined.loc[dist & joined["action_signal"].isin(["BUY", "ADD", "HOLD"]),
               "_target"] *= reduce_factor
    joined.loc[dist & joined["action_signal"].isin(["BUY", "ADD", "HOLD"]),
               "timing_action"] = "REDUCE"

    early = (
        joined["daily_state"].isin(TACTICAL_BULLISH) &
        (joined["action_signal"] == "WAIT") &
        joined["mtf_regime"].isin(EARLY_ENTRY_STATES) &
        (joined["_target"] == 0)
    )
    if early.any():
        joined.loc[early, "_target"] = [
            effective_position(r["mtf_regime"], r["risk_level"], settings)
            for _, r in joined.loc[early].iterrows()]
        joined.loc[early, "timing_action"] = "ENTER"

    # 试多行（tactical_override）遇 DAILY_DISTRIBUTION 同样战术减仓
    joined.loc[dist & joined["is_override"], "_target"] *= reduce_factor
    joined.loc[dist & joined["is_override"], "timing_action"] = "REDUCE"

    # 战术加仓：日线突破时 HOLD/试多 在战略目标基础上 ×1.25（不超 Risk 上限）
    addable = (
        joined["daily_state"].isin(TACTICAL_BULLISH) &
        (joined["mtf_regime"].isin([
            "BULLISH_CONFIRMED", "BULLISH_STABLE", "BULLISH_WARNING",
            "BEARISH_RECOVERY_CANDIDATE"])) &
        (joined["action_signal"].isin(["HOLD", "REDUCE"]) | joined["is_override"])
    )
    if addable.any():
        joined.loc[addable, "_target"] = joined.loc[addable].apply(
            lambda r: min(float(r["_target"]) * add_ratio,
                          risk_cap(r["risk_level"], settings)), axis=1)
        joined.loc[addable & joined["timing_action"].isin(["HOLD", "REDUCE"]),
                   "timing_action"] = "ADD"

    joined["target"] = joined["_target"]
    joined = joined.drop(columns=["_target", "decision_dt", "daily_date_dt"])
    return joined.reset_index(drop=True)
