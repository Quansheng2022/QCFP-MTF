# coding: utf-8
"""Canonical Backtest（QCFP-MTF 2.5：回测与 Live/Shadow 同源）

原则：历史 T 只读取 T 时点可用 Evidence → 唯一决策引擎 →
DecisionSnapshot → target_position → T+1 execution。

本模块把 build_signal_timeline 降级为 Evidence Timeline Builder，
target 一律由 engine.evaluate 产生（与 Shadow / Report / Live 同一引擎）。
"""

import pandas as pd

from ..decision.engine import evaluate


def merge_daily_asof(signals: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    """日线 as-of 并入信号（Q/M/W/D 统一 usable_at <= decision_time）"""
    out = signals.copy()
    if daily is None or daily.empty:
        out["daily_state"] = "DAILY_NEUTRAL"
        return out
    dp = daily.copy()
    dp["decision_dt"] = pd.to_datetime(dp["trade_date"], errors="coerce")
    out["decision_dt"] = pd.to_datetime(out["decision_date"], errors="coerce")
    out = pd.merge_asof(out.sort_values("decision_dt"),
                        dp.sort_values("decision_dt"), on="decision_dt",
                        by="stock_code", direction="backward")
    dcol = "daily_state_y" if "daily_state_y" in out.columns \
        else "daily_state_x" if "daily_state_x" in out.columns \
        else "daily_state"
    out["daily_state"] = out[dcol].fillna("DAILY_NEUTRAL") \
        if dcol in out.columns else "DAILY_NEUTRAL"
    return out


def canonical_replay(signals: pd.DataFrame, settings, run_id="",
                     daily=None, return_snapshots=False):
    """证据时间线 → 唯一引擎有状态重放（prev_state/prev_position 持续演化）

    一次 Evaluate → 一个 DecisionSnapshot；返回带 target/fsm_state 的
    DataFrame，且 return_snapshots=True 时同时返回快照对象列表
    （Ledger 直接消费，禁止二次 Evaluate）。
    """
    df = merge_daily_asof(signals, daily)
    df = df.sort_values(["stock_code", "decision_date"]).reset_index(drop=True)
    prev_state, prev_pos = {}, {}
    targets, fsm_states, base_states, snap_objs = [], [], [], []
    for _, r in df.iterrows():
        code = r["stock_code"]
        ps = prev_state.get(code, "FLAT")
        pp = prev_pos.get(code, 0.0)
        snap = evaluate(dict(r), ps, pp, settings, run_id=run_id)
        prev_state[code] = snap.next_fsm_state
        prev_pos[code] = snap.target_position
        targets.append(snap.target_position)
        fsm_states.append(snap.next_fsm_state)
        base_states.append(snap.base_fsm_state)
        snap_objs.append(snap)
    df["target"] = targets
    df["fsm_state"] = fsm_states
    df["base_fsm_state"] = base_states
    df["engine_source"] = "canonical"
    if return_snapshots:
        return df, snap_objs
    return df
