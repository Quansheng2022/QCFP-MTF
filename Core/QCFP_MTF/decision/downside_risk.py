# coding: utf-8
"""下行风险层（Dynamic Risk Exit / Downside Evidence Score）

定位：战略层（Q/M/W）决定方向，本层只负责"已持仓的风险退出"——
     Downside Risk 的权限必须高于 HOLD：长期 BULLISH 不能阻止风险层减仓。

机制：
    - Downside Evidence Score（DES）：周线破位/趋势/资金/催化剂等负面证据累计
    - 风险下限（Risk Floor）：确认下跌后禁止因"无背离/dq 改善/市场中性"而降风险
    - 滞后解除（Hysteresis）：进入风险容易、解除困难（站回 MA20 + 连续 N 周无破位）
    - 仓位单调性（Monotonicity）：下跌未恢复前目标仓位不得上升
"""

import numpy as np
import pandas as pd

from .position_sizing import risk_cap


def _price_panel(weekly_kl: pd.DataFrame) -> pd.DataFrame:
    df = weekly_kl[["stock_code", "date", "close"]].copy()
    df["week_end"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df = df.sort_values(["stock_code", "week_end"]).reset_index(drop=True)
    g = df.groupby("stock_code")
    df["ma5"] = g["close"].transform(lambda s: s.rolling(5, min_periods=3).mean())
    df["ma10"] = g["close"].transform(lambda s: s.rolling(10, min_periods=5).mean())
    df["ma20"] = g["close"].transform(lambda s: s.rolling(20, min_periods=8).mean())
    df["ma20_slope"] = g["close"].transform(
        lambda s: s.rolling(5, min_periods=3).mean().diff(2))
    df["ret5w"] = df["close"] / g["close"].transform(lambda s: s.shift(5)) - 1
    df["ret13w"] = df["close"] / g["close"].transform(lambda s: s.shift(13)) - 1
    df["peak52"] = g["close"].transform(lambda s: s.rolling(52, min_periods=20).max())
    df["dd52"] = df["close"] / df["peak52"] - 1
    df["decision_dt"] = pd.to_datetime(df["week_end"])
    return df[["stock_code", "decision_dt", "close", "ma5", "ma10", "ma20",
               "ma20_slope", "ret5w", "ret13w", "dd52"]]


def _flow_panel(daily: pd.DataFrame) -> pd.DataFrame:
    df = daily[["stock_code", "trade_date", "d_flow_z", "daily_state"]].copy()
    df["decision_dt"] = pd.to_datetime(df["trade_date"], errors="coerce")
    df = df.dropna(subset=["decision_dt"]).sort_values("decision_dt")
    return df[["stock_code", "decision_dt", "d_flow_z", "daily_state"]]


def apply_downside_risk(signals: pd.DataFrame, weekly_kl: pd.DataFrame,
                        settings: dict, daily: pd.DataFrame = None) -> pd.DataFrame:
    """在信号时间线上叠加下行风险调整（修改 risk_level / target / action_signal）

    需要 signals 含：stock_code / decision_date / tactical_signal /
    catalyst_score / action_signal / risk_level / target。
    """
    cfg = settings.get("decision", {}).get("downside_risk", {})
    out = signals.copy()
    if not cfg.get("enabled", True) or weekly_kl is None or weekly_kl.empty:
        out["des_score"] = 0
        out["des_band"] = "NORMAL"
        out["risk_floor"] = None
        return out

    out["decision_dt"] = pd.to_datetime(out["decision_date"], errors="coerce")
    out = pd.merge_asof(
        out.sort_values("decision_dt"), _price_panel(weekly_kl).sort_values("decision_dt"),
        on="decision_dt", by="stock_code", direction="backward")
    if daily is not None and not daily.empty:
        out = pd.merge_asof(
            out.sort_values("decision_dt"), _flow_panel(daily).sort_values("decision_dt"),
            on="decision_dt", by="stock_code", direction="backward")
    else:
        out["d_flow_z"] = None
        out["daily_state"] = None

    out = out.sort_values(["stock_code", "decision_dt"]).reset_index(drop=True)
    out["_bd"] = (out["tactical_signal"] == "Breakdown").astype(int)
    out["bd_streak"] = out.groupby("stock_code")["_bd"].transform(
        lambda s: s.groupby((s != s.shift()).cumsum()).cumsum())

    w = cfg.get("weights", {})
    score = np.zeros(len(out), dtype=float)
    score += (out["_bd"] == 1) * float(w.get("breakdown", 2))
    score += (out["bd_streak"] >= 2) * float(w.get("breakdown_streak", 1))
    score += (out["close"] < out["ma20"]).fillna(False) * float(w.get("below_ma20", 1))
    score += (out["ma5"] < out["ma10"]).fillna(False) * float(w.get("ma5_lt_ma10", 1))
    score += (out["ma20_slope"] < 0).fillna(False) * float(w.get("ma20_slope_neg", 1))
    score += (out["d_flow_z"] < 0).fillna(False) * float(w.get("flow_neg", 1))
    score += (out["d_flow_z"] < -1).fillna(False) * float(w.get("flow_neg2", 1))
    score += (out["daily_state"] == "DAILY_DECLINE").fillna(False) * float(w.get("daily_decline", 2))
    score += (out["catalyst_score"] < 0).fillna(False) * float(w.get("cqs_neg", 1))
    score += (out["ret5w"] < -0.05).fillna(False) * float(w.get("ret5w_neg", 1))
    score += (out["ret13w"] < -0.10).fillna(False) * float(w.get("ret13w_neg", 1))
    score += (out["dd52"] < -0.15).fillna(False) * float(w.get("dd52_neg", 1))
    out["des_score"] = score.round(0).astype(int)
    out["des_band"] = out["des_score"].map(
        lambda s: "NORMAL" if s <= 2 else ("WATCH" if s <= 4
                                           else ("REDUCE" if s <= 6 else "DE-RISK")))

    floor = str(cfg.get("breakdown_risk_floor", "Extreme"))
    release_weeks = int(cfg.get("release_weeks", 2))
    exit_at = int(cfg.get("exit_at_score", 7))
    rank = {"Low": 0, "Medium": 1, "High": 2, "Extreme": 3}
    new_risk = out["risk_level"].astype(str).to_numpy(copy=True)
    new_target = out["target"].astype(float).to_numpy(copy=True)
    new_action = out["action_signal"].to_numpy(copy=True)
    floor_active = np.zeros(len(out), dtype=bool)
    for code, idx in out.groupby("stock_code", sort=False).indices.items():
        idx = sorted(idx)
        active, streak, max_t = False, 0, 0.0
        for i in idx:
            bd = bool(out.at[i, "_bd"])
            close, ma20 = out.at[i, "close"], out.at[i, "ma20"]
            below = bool(pd.notna(close) and pd.notna(ma20) and close < ma20)
            des = int(out.at[i, "des_score"])
            if active:
                if below or bd:
                    streak = 0
                else:
                    streak += 1
                if (not below) and (not bd) and streak >= release_weeks:
                    active, streak, max_t = False, 0, 0.0
                    continue
                floor_active[i] = True
                new_risk[i] = max(new_risk[i], floor, key=lambda x: rank.get(x, 3))
                capped = min(new_target[i], risk_cap(new_risk[i], settings))
                max_t = max(max_t, capped)
                new_target[i] = min(capped, max_t)
                if new_action[i] == "HOLD":
                    new_action[i] = "REDUCE"
                if des >= exit_at:
                    new_target[i], new_action[i] = 0.0, "EXIT"
            else:
                if (bd and below) or des >= 5:
                    floor_active[i] = True
                    new_risk[i] = max(new_risk[i], floor, key=lambda x: rank.get(x, 3))
                    capped = min(new_target[i], risk_cap(new_risk[i], settings))
                    active, streak, max_t = True, 0, capped
                    new_target[i] = min(capped, max_t)
                    if new_action[i] == "HOLD":
                        new_action[i] = "REDUCE"
                    if des >= exit_at:
                        new_target[i], new_action[i] = 0.0, "EXIT"

    out["risk_floor"] = np.where(floor_active, floor, None)
    out["risk_level"] = new_risk
    out["target"] = new_target
    out["action_signal"] = new_action
    out = out.drop(columns=["_bd", "decision_dt"])
    return out
