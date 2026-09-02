#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF 2.2 —— Permission + FSM Ablation（A/B/C/D 双轨验证）

    Model A0：Legacy（当前管道 target）
    Model A1：Legacy + Permission Cap（target=min(legacy, cap_position)，非二值门）
    Model A2：FSM（无权限门，默认 STRONG_ALLOW）
    Model A3：FSM + Soft Exit（RISK_EXIT / BREAKDOWN）
    Model A4：FSM + Hard Exit
    Model A5：Permission + FSM
    Model A6：Permission + FSM + Soft Exit
    Model A7：Permission + FSM + Hard Exit
    Model A8：Permission + FSM + Soft Exit + Hard Exit（完整 2.2，含 Daily）
    Model A9：A8 − Daily（Full − Daily，测 Daily 对波段捕获的贡献）
    Model A10：A8 − Participation Budget（Full − 参与预算，测四层中间层贡献）
    Model A11：A8 − Market Scale（Full − 市场环境预算缩放，保留 Market Context）
    Model A12：A8 − Stop（Full − 决策链止损事件，孤立 Stop 贡献）
    Model A13：A8 − Observation（Full − 观察仓，孤立探索性暴露贡献）

    正交 Ablation（2.3）：每次只改变一个模块，报告单模块效应与交互项：
        Permission effect = A5 − A2；FSM effect = A2 − A0；
        Soft Exit effect = A3 − A2；Hard Exit effect = A4 − A2；
        Interaction(Permission, FSM) = A5 − A1 − A2 + A0。

指标：年化 / Sharpe / MDD / PF / 换手 / 平均暴露 / 上行捕获 / 下行捕获。
研究假设：Permission 的价值 = Risk Filtering（↓MDD/↓下行捕获/↓换手），
          FSM 的价值 = Entry/Exit 质量（↑MFE/↓MAE——MAE/MFE 见 daily_alpha_test）。
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

import pandas as pd

from QCFP_MTF.backtest.benchmark import buy_hold_returns
from QCFP_MTF.backtest.data_pipeline import build_signal_timeline
from QCFP_MTF.backtest.engine import portfolio_returns, run_backtest
from QCFP_MTF.backtest.performance import evaluate as evaluate_perf
from QCFP_MTF.backtest.wave_capture import (false_entry_rate, find_waves,
                                            wave_capture_metrics,
                                            wave_capture_summary)
from QCFP_MTF.common.db import connect
from QCFP_MTF.common.logger import setup_logger
from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.config.settings import load_qcfp_settings
from QCFP_MTF.data.loader import load_derived, load_idx_hist, load_kline
from QCFP_MTF.decision.hard_exit import ExitEvent
from QCFP_MTF.decision.engine import DecisionConfig, evaluate as evaluate_decision
from QCFP_MTF.decision.institutional_permission import evaluate_institutional_permission
from QCFP_MTF.decision.permission_policy import (PERMISSION_POSITION_CAP,
                                                 permission_state_violation)


def _capture(bt, weekly_kl):
    strat = bt.groupby("week_end")["pnl"].mean().rename("strat")
    bench = buy_hold_returns(weekly_kl).rename("mkt")
    j = pd.concat([strat, bench], axis=1).dropna()
    up, dn = j[j["mkt"] > 0], j[j["mkt"] < 0]
    return {
        "upside_capture": round(float(up["strat"].mean() / up["mkt"].mean()), 4)
        if len(up) else None,
        "downside_capture": round(float(dn["strat"].mean() / dn["mkt"].mean()), 4)
        if len(dn) else None,
    }


def _permission_series(signals, settings):
    return [
        evaluate_institutional_permission(
            c_state=r["c_state"], f_state=r["f_state"], p_state=r["p_state"],
            persistence=(2 if r["f_state"] == "F↑" and r.get("prev_f_state") == "F↑"
                         else 1 if r["f_state"] == "F↑" else 0),
            confidence=r.get("chip_stability_confidence") or "Medium",
            data_quality=r.get("data_quality") or "B", settings=settings).permission
        for _, r in signals.iterrows()]


def _filter_exit_event(ev, use_soft_exit, use_hard_exit):
    """按实验配置裁剪 Exit Event（A2 全关 / A3 仅软 / A4 全开）"""
    if ev.kind == "NONE":
        return ev
    if ev.hard:
        return ev if use_hard_exit else ExitEvent("NONE")
    return ev if use_soft_exit else ExitEvent("NONE")


def _fsm_targets(signals, settings, use_permission, use_soft_exit=False,
                 use_hard_exit=False, use_daily=True, use_budget=True,
                 use_market_scale=True, use_stop=True, use_observation=True):
    """Ablation 专用重放：统一走唯一决策引擎 engine.evaluate

    不再自行拼 FSM+Permission+Sizing；模块开关通过 DecisionConfig 传入引擎。
    """
    df = signals.sort_values(["stock_code", "decision_date"]).copy()
    config = DecisionConfig(use_permission=use_permission,
                            use_soft_exit=use_soft_exit,
                            use_hard_exit=use_hard_exit,
                            use_daily=use_daily,
                            use_budget=use_budget,
                            use_market_scale=use_market_scale,
                            use_stop=use_stop,
                            use_observation=use_observation)
    states, targets, violations, risk_inc_violations = [], [], [], []
    permissions, prev_states, exit_events = [], [], []
    prev_state_by_code = {}
    for code, g in df.groupby("stock_code", sort=False):
        state, cur = prev_state_by_code.get(code, "FLAT"), 0.0
        for _, r in g.iterrows():
            prev_pos = cur
            snap = evaluate_decision(dict(r), state, prev_pos, settings,
                                     config=config, run_id="ablation")
            prev_states.append(state)
            state = snap.next_fsm_state
            cur = snap.target_position
            states.append(state)
            targets.append(cur)
            permissions.append(snap.institutional_permission)
            exit_events.append(snap.exit_event_kind)
            violations.append(permission_state_violation(
                snap.institutional_permission, state, cur))
            risk_inc_violations.append(
                snap.institutional_permission in ("BLOCK", "WATCH")
                and cur > prev_pos + 1e-9)
        prev_state_by_code[code] = state
    df["fsm_state"] = states
    df["new_target"] = targets
    df["perm_violation"] = violations
    df["risk_increase_violation"] = risk_inc_violations
    df["permission"] = permissions
    df["prev_fsm_state"] = prev_states
    df["exit_event"] = exit_events
    return df


def _illegal_jump(prev, nxt):
    """状态跳跃检测（冻结阶梯 FLAT→TESTING→BUILDING→HOLDING→TRIMMING→EXITING→COOLDOWN）"""
    if prev == nxt:
        return False
    if prev in ("FLAT", "TESTING", "BUILDING", "HOLDING", "TRIMMING"):
        if nxt in ("BUILDING", "HOLDING") and prev == "FLAT":
            return True
        if nxt == "HOLDING" and prev == "TESTING":
            return True
        if nxt == "FLAT" and prev not in ("COOLDOWN",):
            return True
    return False


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF 2.2 Permission/FSM Ablation")
    parser.add_argument("--start", default="2021-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument("--stock", default=None)
    parser.add_argument("--wave-year", type=int, default=None)
    parser.add_argument("--wave-min-gain", type=float, default=0.5)
    parser.add_argument("--wave-window", type=int, default=26)
    args = parser.parse_args(argv)
    settings = load_qcfp_settings()
    logger = setup_logger("permission_fsm_ablation",
                          log_file="permission_fsm_ablation.log", mode="a")
    logger.info("=== Permission + FSM Ablation 启动 ===")

    structural = pd.read_sql_query(
        "SELECT stock_code, stock_name, period_end, available_date, structural_regime, "
        "c_state, f_state, p_state, q_trend_score, q_position_52w, data_quality "
        "FROM qcfp_quarterly_structural", connect())
    monthly = pd.read_sql_query(
        "SELECT stock_code, month_end, monthly_behavior_state, cbi_score, cbi_state, "
        "cost_position, data_quality FROM qcfp_monthly_behavior", connect())
    weekly = pd.read_sql_query(
        "SELECT stock_code, stock_name, week_end, tactical_signal, data_quality "
        "FROM qcfp_weekly_tactical", connect())
    chip = load_derived("quarterly_chip_analysis")[["stock_code", "quarter_end_date",
                                                    "chip_structure_score"]]
    idx = load_idx_hist()
    weekly_kl = load_kline("weekly")
    daily = pd.read_sql_query(
        "SELECT stock_code, trade_date, daily_state, d_flow_z "
        "FROM qcfp_daily_tactical", connect())
    end = args.end or weekly["week_end"].max()
    stocks = [args.stock] if args.stock else None
    sig = build_signal_timeline(structural, monthly, weekly, chip, idx, settings,
                                stocks=stocks, weekly_kl=weekly_kl, daily=daily)
    # as-of 日线状态（供 FSM Daily 触发）
    dp = daily.copy()
    dp["decision_dt"] = pd.to_datetime(dp["trade_date"])
    sig["decision_dt"] = pd.to_datetime(sig["decision_date"])
    sig = pd.merge_asof(sig.sort_values("decision_dt"), dp.sort_values("decision_dt"),
                        on="decision_dt", by="stock_code", direction="backward")
    dcol = "daily_state_y" if "daily_state_y" in sig.columns \
        else "daily_state_x" if "daily_state_x" in sig.columns else "daily_state"
    sig["daily_state"] = sig[dcol].fillna("DAILY_NEUTRAL") \
        if dcol in sig.columns else "DAILY_NEUTRAL"
    # 2024 大波段 Replay：识别波段并按模型逐一测算捕获指标
    waves = find_waves(weekly_kl, min_gain=args.wave_min_gain,
                       window=args.wave_window)
    if args.wave_year:
        waves = waves[waves["start_date"].str.startswith(str(args.wave_year))]
    if args.stock:
        waves = waves[waves["stock_code"] == args.stock]
    logger.info(f"Wave Replay：{len(waves)} 个波段"
                f"（≥{args.wave_min_gain:.0%}，{args.wave_window} 周窗口"
                + (f"，起始年 {args.wave_year}" if args.wave_year else "") + "）")

    fsm_no_perm = _fsm_targets(sig, settings, use_permission=False)                     # A2
    fsm_no_perm_soft = _fsm_targets(sig, settings, use_permission=False,
                                    use_soft_exit=True, use_hard_exit=False)            # A3
    fsm_no_perm_hard = _fsm_targets(sig, settings, use_permission=False,
                                    use_soft_exit=False, use_hard_exit=True)            # A4
    fsm_perm = _fsm_targets(sig, settings, use_permission=True)                         # A5
    fsm_perm_soft = _fsm_targets(sig, settings, use_permission=True,
                                 use_soft_exit=True, use_hard_exit=False)               # A6
    fsm_perm_hard = _fsm_targets(sig, settings, use_permission=True,
                                 use_soft_exit=False, use_hard_exit=True)               # A7
    fsm_full = _fsm_targets(sig, settings, use_permission=True,
                            use_soft_exit=True, use_hard_exit=True)                     # A8
    fsm_no_daily = _fsm_targets(sig, settings, use_permission=True,
                                use_soft_exit=True, use_hard_exit=True,
                                use_daily=False)                                       # A9
    fsm_no_budget = _fsm_targets(sig, settings, use_permission=True,
                                 use_soft_exit=True, use_hard_exit=True,
                                 use_budget=False)                                     # A10
    fsm_no_mkt = _fsm_targets(sig, settings, use_permission=True,
                              use_soft_exit=True, use_hard_exit=True,
                              use_market_scale=False)                                  # A11
    fsm_no_stop = _fsm_targets(sig, settings, use_permission=True,
                               use_soft_exit=True, use_hard_exit=True,
                               use_stop=False)                                         # A12
    fsm_no_obs = _fsm_targets(sig, settings, use_permission=True,
                              use_soft_exit=True, use_hard_exit=True,
                              use_observation=False)                                   # A13
    perm = _permission_series(sig, settings)
    models = {
        "A0_Legacy": sig["target"].to_numpy(),
        "A1_PermCap": [min(t, PERMISSION_POSITION_CAP.get(p, 0.0))
                       for p, t in zip(perm, sig["target"])],
        "A2_FSM": fsm_no_perm["new_target"].to_numpy(),
        "A3_FSM_SoftExit": fsm_no_perm_soft["new_target"].to_numpy(),
        "A4_FSM_HardExit": fsm_no_perm_hard["new_target"].to_numpy(),
        "A5_PermFSM": fsm_perm["new_target"].to_numpy(),
        "A6_PermFSM_SoftExit": fsm_perm_soft["new_target"].to_numpy(),
        "A7_PermFSM_HardExit": fsm_perm_hard["new_target"].to_numpy(),
        "A8_PermFSM_FullExit": fsm_full["new_target"].to_numpy(),
        "A9_FullNoDaily": fsm_no_daily["new_target"].to_numpy(),
        "A10_FullNoBudget": fsm_no_budget["new_target"].to_numpy(),
        "A11_FullNoMarketScale": fsm_no_mkt["new_target"].to_numpy(),
        "A12_FullNoStop": fsm_no_stop["new_target"].to_numpy(),
        "A13_FullNoObservation": fsm_no_obs["new_target"].to_numpy(),
    }
    rows = []
    fsm_src = {"A2_FSM": fsm_no_perm, "A3_FSM_SoftExit": fsm_no_perm_soft,
               "A4_FSM_HardExit": fsm_no_perm_hard, "A5_PermFSM": fsm_perm,
               "A6_PermFSM_SoftExit": fsm_perm_soft,
               "A7_PermFSM_HardExit": fsm_perm_hard,
               "A8_PermFSM_FullExit": fsm_full,
                   "A9_FullNoDaily": fsm_no_daily,
                   "A10_FullNoBudget": fsm_no_budget,
                   "A11_FullNoMarketScale": fsm_no_mkt,
               "A12_FullNoStop": fsm_no_stop,
               "A13_FullNoObservation": fsm_no_obs}
    category_map = {
        "A0_Legacy": "alpha_legacy", "A1_PermCap": "alpha_legacy",
        "A2_FSM": "retail_fsm", "A3_FSM_SoftExit": "retail_fsm",
        "A4_FSM_HardExit": "retail_fsm",
        "A5_PermFSM": "governance", "A6_PermFSM_SoftExit": "governance",
        "A7_PermFSM_HardExit": "governance",
        "A8_PermFSM_FullExit": "governance",
        "A9_FullNoDaily": "governance", "A10_FullNoBudget": "governance",
        "A11_FullNoMarketScale": "governance",
        "A12_FullNoStop": "governance", "A13_FullNoObservation": "governance",
    }
    for name, target in models.items():
        s = sig.copy()
        s["target"] = target
        if name in fsm_src:
            # 2.4 趋势存活权：回测引擎按 fsm_state 给 HOLDING 更宽存活缓冲
            s["fsm_state"] = fsm_src[name]["fsm_state"]
        bt = run_backtest(s, weekly_kl, settings, start=args.start, end=end)
        port = portfolio_returns(bt)
        perf = evaluate_perf(port["portfolio_return"],
                             turnover=port["avg_turnover"])
        cap = _capture(bt, weekly_kl)
        risk_map = sig[["stock_code", "decision_date", "risk_level"]].rename(
            columns={"decision_date": "week_end"})
        bt_r = bt.merge(risk_map, on=["stock_code", "week_end"], how="left")
        overall_exp = float(bt_r["position_start"].mean())
        high_exp = float(bt_r.loc[bt_r["risk_level"].isin(["High", "Extreme"]),
                                  "position_start"].mean()) if len(bt_r) else 0.0
        churn = float(bt["turnover"].mean())
        # Wave Capture（2024 大波段）
        wm = wave_capture_metrics(bt, waves)
        ws = wave_capture_summary(wm)
        wave_q = {
            "wave_n": ws["n_waves"],
            "wave_participated": ws.get("participated"),
            "wave_missed_rate": ws.get("missed_wave_rate"),
            "wave_capture_ratio": ws.get("capture_ratio_mean"),
            "wave_entry_delay": ws.get("entry_delay_mean_weeks"),
            "wave_mfe": ws.get("mfe_mean"),
            "wave_mae": ws.get("mae_mean"),
            "wave_false_entry_rate": false_entry_rate(bt, waves),
        }
        # 决策质量（仅 FSM 模型）
        q = {}
        if name in fsm_src:
            src = fsm_src[name]
            transitions = (
                src["prev_fsm_state"].astype(str) + "→"
                + src["fsm_state"]).value_counts().to_dict()
            mechanism = {
                "permission_dist": src["permission"].value_counts().to_dict(),
                "transition_dist": transitions,
                "target_positive_rate": round(
                    float((src["new_target"] > 0).mean()), 4),
                "exit_dist": src["exit_event"].value_counts().to_dict(),
                "mean_target": round(float(src["new_target"].mean()), 4),
            }
            q["perm_violations"] = int(src["perm_violation"].sum())
            q["risk_increase_violations"] = int(
                src["risk_increase_violation"].sum())
            def _jumps(g):
                return sum(_illegal_jump(a, b) for a, b in zip(
                    g["fsm_state"].shift(1).fillna("FLAT"), g["fsm_state"]))
            q["illegal_jumps"] = int(sum(_jumps(g)
                                         for _, g in src.groupby("stock_code")))
        rows.append({
            "model": name,
            "category": category_map.get(name, "research"),
            "annualized_return": perf.get("annualized_return"),
            "sharpe": perf.get("sharpe"),
            "max_drawdown": perf.get("max_drawdown"),
            "profit_factor": perf.get("profit_factor"),
            "annual_turnover": perf.get("annual_turnover"),
            "churn": round(churn, 4),
            **q,
            "avg_exposure": round(float(bt["position_start"].mean()), 4),
            "exposure_efficiency": round(float(perf.get("annualized_return") or 0) / overall_exp, 4)
            if overall_exp > 0 else None,
            "bad_exposure_ratio": round(high_exp / overall_exp, 4)
            if overall_exp > 0 else None,
            **cap,
            **wave_q,
            "mechanism": mechanism if name in fsm_src else None,
        })
        logger.info(
            f"{name}: 年化 {perf['annualized_return']:.2%}  Sharpe {perf['sharpe']}  "
            f"回撤 {perf['max_drawdown']:.2%}  PF {perf['profit_factor']}  "
            f"换手 {perf['annual_turnover']:.2f}  暴露 {rows[-1]['avg_exposure']:.1%}  "
            f"暴露效率 {rows[-1]['exposure_efficiency']}  "
            f"坏暴露比 {rows[-1]['bad_exposure_ratio']}  "
            f"波段捕获 {ws.get('capture_ratio_mean')}"
            f"（{ws.get('participated')}/{ws['n_waves']}，"
            f"错失 {ws.get('missed_wave_rate')}，"
            f"延迟 {ws.get('entry_delay_mean_weeks')} 周）  "
            f"{('越权 ' + str(q['perm_violations']) + ' 跳跃 ' + str(q['illegal_jumps']))
               if q else ''}  "
            f"上行 {cap['upside_capture']} 下行 {cap['downside_capture']}")

    result = pd.DataFrame(rows)
    report_root = get_report_root() / "backtest"
    report_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    import hashlib
    shared_input_hash = hashlib.sha256(
        sig[["stock_code", "decision_date", "target"]].to_csv(index=False)
        .encode("utf-8")).hexdigest()[:16]
    shared_settings_hash = hashlib.sha256(
        json.dumps(settings, sort_keys=True, default=str)
        .encode("utf-8")).hexdigest()[:12]
    # 正交效应：单模块增量 + 交互项（年化收益口径）
    def _ann(model_name):
        r = result.loc[result["model"] == model_name, "annualized_return"]
        return float(r.iloc[0]) if len(r) and r.iloc[0] is not None else None

    def _delta(a, b):
        x, y = _ann(a), _ann(b)
        return round(x - y, 6) if x is not None and y is not None else None

    effects = {
        "permission_effect_A5_A2": _delta("A5_PermFSM", "A2_FSM"),
        "fsm_effect_A2_A0": _delta("A2_FSM", "A0_Legacy"),
        "soft_exit_effect_A3_A2": _delta("A3_FSM_SoftExit", "A2_FSM"),
        "hard_exit_effect_A4_A2": _delta("A4_FSM_HardExit", "A2_FSM"),
        "daily_effect_A8_A9": _delta("A8_PermFSM_FullExit",
                                     "A9_FullNoDaily"),
    }
    a5, a1, a2, a0 = map(_ann,
                         ("A5_PermFSM", "A1_PermCap", "A2_FSM", "A0_Legacy"))
    if all(v is not None for v in (a5, a1, a2, a0)):
        effects["interaction_perm_fsm_A5_A1_A2_A0"] = round(
            a5 - a1 - a2 + a0, 6)
    a6, a3 = _ann("A6_PermFSM_SoftExit"), _ann("A3_FSM_SoftExit")
    if all(v is not None for v in (a6, a5, a3, a2)):
        effects["interaction_perm_softexit_(A6-A5)-(A3-A2)"] = round(
            (a6 - a5) - (a3 - a2), 6)
    a7, a4 = _ann("A7_PermFSM_HardExit"), _ann("A4_FSM_HardExit")
    if all(v is not None for v in (a7, a5, a4, a2)):
        effects["interaction_perm_hardexit_(A7-A5)-(A4-A2)"] = round(
            (a7 - a5) - (a4 - a2), 6)

    # 机构过滤价值（IFV）：用"避免坏交易"衡量，而非单纯收益
    def _metric2(a, b, key):
        x, y = _metric(a, key), _metric(b, key)
        return round(x - y, 4) if x is not None and y is not None else None

    mdd_d = _metric2("A5_PermFSM", "A2_FSM", "max_drawdown")
    mae_d = _metric2("A5_PermFSM", "A2_FSM", "wave_mae")
    fe_d = _metric2("A5_PermFSM", "A2_FSM", "wave_false_entry_rate")
    miss_d = _metric2("A5_PermFSM", "A2_FSM", "wave_missed_rate")
    ifv = None
    if all(v is not None for v in (mdd_d, mae_d, fe_d, miss_d)):
        # ΔMDD 改善 + ΔMAE 改善 + ΔFalseEntry 改善 − λ(0.5)×ΔMissed 机会
        ifv = round(mdd_d + mae_d + fe_d - 0.5 * miss_d, 4)
    effects["institutional_filter_value_A5_A2"] = ifv
    contributions["institutional_filter_value_A5_A2"] = {
        "ifv": ifv,
        "delta_mdd": mdd_d, "delta_mae": mae_d,
        "delta_false_entry": fe_d, "delta_missed_opportunity": miss_d,
        "lambda_missed": 0.5,
    }
    # 贡献分解：机构过滤器 / 散户波段系统 / 各退出层（整体 + 2024 大波段）
    def _metric(model_name, key):
        r = result.loc[result["model"] == model_name, key]
        return float(r.iloc[0]) if len(r) and r.iloc[0] is not None else None

    def _mdelta(a, b, key):
        x, y = _metric(a, key), _metric(b, key)
        return round(x - y, 6) if x is not None and y is not None else None

    contributions = {
        "institutional_filter_A5-A2": {
            "overall_annualized_delta": _delta("A5_PermFSM", "A2_FSM"),
            "wave_capture_ratio_delta": _mdelta(
                "A5_PermFSM", "A2_FSM", "wave_capture_ratio"),
            "wave_missed_rate_delta": _mdelta(
                "A5_PermFSM", "A2_FSM", "wave_missed_rate"),
            "wave_entry_delay_delta": _mdelta(
                "A5_PermFSM", "A2_FSM", "wave_entry_delay"),
        },
        "retail_fsm_A2-A0": {
            "overall_annualized_delta": _delta("A2_FSM", "A0_Legacy"),
            "wave_capture_ratio_delta": _mdelta(
                "A2_FSM", "A0_Legacy", "wave_capture_ratio"),
            "wave_missed_rate_delta": _mdelta(
                "A2_FSM", "A0_Legacy", "wave_missed_rate"),
            "wave_entry_delay_delta": _mdelta(
                "A2_FSM", "A0_Legacy", "wave_entry_delay"),
        },
        "soft_exit_A3-A2": {
            "overall_annualized_delta": _delta("A3_FSM_SoftExit", "A2_FSM"),
            "wave_capture_ratio_delta": _mdelta(
                "A3_FSM_SoftExit", "A2_FSM", "wave_capture_ratio"),
        },
        "hard_exit_A4-A2": {
            "overall_annualized_delta": _delta("A4_FSM_HardExit", "A2_FSM"),
            "wave_capture_ratio_delta": _mdelta(
                "A4_FSM_HardExit", "A2_FSM", "wave_capture_ratio"),
        },
        "daily_A8-A9": {
            "overall_annualized_delta": _delta(
                "A8_PermFSM_FullExit", "A9_FullNoDaily"),
            "wave_capture_ratio_delta": _mdelta(
                "A8_PermFSM_FullExit", "A9_FullNoDaily", "wave_capture_ratio"),
        },
        "participation_budget_A8-A10": {
            "overall_annualized_delta": _delta(
                "A8_PermFSM_FullExit", "A10_FullNoBudget"),
            "wave_capture_ratio_delta": _mdelta(
                "A8_PermFSM_FullExit", "A10_FullNoBudget",
                "wave_capture_ratio"),
            "wave_missed_rate_delta": _mdelta(
                "A8_PermFSM_FullExit", "A10_FullNoBudget",
                "wave_missed_rate"),
            "wave_entry_delay_delta": _mdelta(
                "A8_PermFSM_FullExit", "A10_FullNoBudget",
                "wave_entry_delay"),
        },
        "market_scale_A8-A11": {
            "overall_annualized_delta": _delta(
                "A8_PermFSM_FullExit", "A11_FullNoMarketScale"),
            "wave_capture_ratio_delta": _mdelta(
                "A8_PermFSM_FullExit", "A11_FullNoMarketScale",
                "wave_capture_ratio"),
            "wave_missed_rate_delta": _mdelta(
                "A8_PermFSM_FullExit", "A11_FullNoMarketScale",
                "wave_missed_rate"),
        },
        "stop_effect_A8-A12": {
            "overall_annualized_delta": _delta(
                "A8_PermFSM_FullExit", "A12_FullNoStop"),
            "wave_capture_ratio_delta": _mdelta(
                "A8_PermFSM_FullExit", "A12_FullNoStop",
                "wave_capture_ratio"),
            "wave_missed_rate_delta": _mdelta(
                "A8_PermFSM_FullExit", "A12_FullNoStop",
                "wave_missed_rate"),
        },
        "observation_effect_A8-A13": {
            "overall_annualized_delta": _delta(
                "A8_PermFSM_FullExit", "A13_FullNoObservation"),
            "wave_capture_ratio_delta": _mdelta(
                "A8_PermFSM_FullExit", "A13_FullNoObservation",
                "wave_capture_ratio"),
            "wave_missed_rate_delta": _mdelta(
                "A8_PermFSM_FullExit", "A13_FullNoObservation",
                "wave_missed_rate"),
        },
    }
    (report_root / f"permission_fsm_ablation_{stamp}.json").write_text(
        json.dumps({"generated_at": stamp,
                    "schema_version": "1.1",
                    "effects": effects,
                    "wave_replay": {
                        "year": args.wave_year,
                        "min_gain": args.wave_min_gain,
                        "window_weeks": args.wave_window,
                        "focus_stock": args.stock,
                        "n_waves": int(len(waves)),
                        "contributions": contributions,
                    },
                    "experiment": {
                        "shared_input_hash": shared_input_hash,
                        "shared_settings_hash": shared_settings_hash,
                        "modules": {
                            "A0": {"permission": False, "fsm": False,
                                   "soft_exit": False, "hard_exit": False},
                            "A1": {"permission": "cap_only", "fsm": False,
                                   "soft_exit": False, "hard_exit": False},
                            "A2": {"permission": False, "fsm": True,
                                   "soft_exit": False, "hard_exit": False},
                            "A3": {"permission": False, "fsm": True,
                                   "soft_exit": True, "hard_exit": False},
                            "A4": {"permission": False, "fsm": True,
                                   "soft_exit": False, "hard_exit": True},
                            "A5": {"permission": True, "fsm": True,
                                   "soft_exit": False, "hard_exit": False},
                            "A6": {"permission": True, "fsm": True,
                                   "soft_exit": True, "hard_exit": False},
                            "A7": {"permission": True, "fsm": True,
                                   "soft_exit": False, "hard_exit": True},
                            "A8": {"permission": True, "fsm": True,
                                   "soft_exit": True, "hard_exit": True,
                                   "daily": True},
                            "A9": {"permission": True, "fsm": True,
                                   "soft_exit": True, "hard_exit": True,
                                   "daily": False},
                            "A10": {"permission": True, "fsm": True,
                                    "soft_exit": True, "hard_exit": True,
                                    "daily": True, "budget": False},
                            "A11": {"permission": True, "fsm": True,
                                    "soft_exit": True, "hard_exit": True,
                                    "daily": True, "budget": True,
                                    "market_scale": False},
                            "A12": {"permission": True, "fsm": True,
                                    "soft_exit": True, "hard_exit": True,
                                    "daily": True, "budget": True,
                                    "market_scale": True, "stop": False},
                            "A13": {"permission": True, "fsm": True,
                                    "soft_exit": True, "hard_exit": True,
                                    "daily": True, "budget": True,
                                    "market_scale": True,
                                    "observation": False},
                        },
                    },
                    "models": result.to_dict(orient="records")},
                   ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    result.to_csv(report_root / f"permission_fsm_ablation_{stamp}.csv",
                  index=False, encoding="utf-8-sig")
    if args.wave_year or args.wave_min_gain:
        md = ["# QCFP-MTF Ablation × 大波段 Replay\n",
              f"- 生成时间：{stamp}　焦点：{args.stock or '全部'}　"
              f"波段≥{args.wave_min_gain:.0%}（{args.wave_window} 周）"
              + (f"　起始年 {args.wave_year}" if args.wave_year else "") + "\n",
              f"- 波段数：{int(len(waves))}\n",
              "## 各模型 2024 大波段捕获\n",
              "| 模型 | 年化 | MDD | 参与 | 错失率 | 捕获比 | 进入延迟 | MFE | MAE | 错误试仓率 |",
              "| :-- | --: | --: | --: | --: | --: | --: | --: | --: | --: |"]
        for _, r in result.iterrows():
            md.append(
                f"| {r['model']} | {r['annualized_return']:.2%} | "
                f"{r['max_drawdown']:.2%} | {r.get('wave_participated')} | "
                f"{r.get('wave_missed_rate')} | {r.get('wave_capture_ratio')} | "
                f"{r.get('wave_entry_delay')} | {r.get('wave_mfe')} | "
                f"{r.get('wave_mae')} | {r.get('wave_false_entry_rate')} |")
        md += ["\n## 贡献分解\n",
               "| 模块 | 口径 | 年化增量 | 捕获比增量 | 错失率增量 | 进入延迟增量 |",
               "| :-- | :-- | --: | --: | --: | --: |"]
        for key, c in contributions.items():
            md.append(
                f"| {key} | {c.get('overall_annualized_delta')} | "
                f"{c.get('wave_capture_ratio_delta')} | "
                f"{c.get('wave_missed_rate_delta')} | "
                f"{c.get('wave_entry_delay_delta')} |")
        (report_root / f"permission_fsm_ablation_wave_{stamp}.md").write_text(
            "\n".join(md), encoding="utf-8")
        logger.info(f"Wave 报告已保存: permission_fsm_ablation_wave_{stamp}.md")
    logger.info(f"报告已保存: Report/QCFP_MTF/backtest/permission_fsm_ablation_{stamp}.{{json,csv}}")
    logger.info("permission_fsm_ablation 完成 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
