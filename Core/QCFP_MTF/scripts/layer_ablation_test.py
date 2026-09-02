#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF —— 层级消融实验（Layer Ablation / 增量贡献矩阵）

Model Q      ：仅季度结构（BULLISH族→1.0 / DIVERGENCE→0.5 / BOTTOM→0.2 / 空头→0）
Model QM     ：Q × 月线阶段门（Improving 1.0 / Stable 0.75 / Deteriorating 0.5）
Model QMW    ：完整 MTF 管道（关闭战术覆盖）
Model Full   ：QMW + 方案 B 战术覆盖（当前默认）

输出：年化/Sharpe/MDD/PF/换手/成本 + 13 周 Rank IC + Full 模型试多专项统计
     + 01951 2024 波段收益（每层）。
"""

import argparse
import copy
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

import pandas as pd

from QCFP_MTF.backtest.data_pipeline import build_signal_timeline
from QCFP_MTF.backtest.benchmark import buy_hold_returns
from QCFP_MTF.backtest.engine import portfolio_returns, run_backtest
from QCFP_MTF.backtest.performance import evaluate
from QCFP_MTF.common.db import connect
from QCFP_MTF.common.logger import setup_logger
from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.config.settings import load_qcfp_settings
from QCFP_MTF.data.loader import load_derived, load_idx_hist, load_kline

BULLISH_BASE = {"STRUCTURAL_BULLISH": 1.0, "STRUCTURAL_ACCUMULATION": 1.0,
                "STRUCTURAL_DIVERGENCE": 0.5, "STRUCTURAL_BOTTOM_CANDIDATE": 0.2}
STAGE_FACTOR = {"Improving": 1.0, "Stable": 0.75, "Deteriorating": 0.5}


def _q_target(df):
    return df["structural_regime"].map(BULLISH_BASE).fillna(0.0)


def _qm_target(df):
    base = _q_target(df)
    f = df["monthly_behavior_state"].map(STAGE_FACTOR).fillna(0.5)
    return (base * f).clip(upper=1.0)


def rank_ic(signals, weekly_kl, horizon=13):
    kl = weekly_kl[["stock_code", "date", "close"]].copy()
    kl["week_end"] = pd.to_datetime(kl["date"]).dt.strftime("%Y-%m-%d")
    kl = kl.sort_values(["stock_code", "week_end"])
    kl["fwd"] = kl.groupby("stock_code")["close"].shift(-horizon) / kl["close"] - 1
    panel = signals[["stock_code", "decision_date", "target"]].merge(
        kl[["stock_code", "week_end", "fwd"]],
        left_on=["stock_code", "decision_date"],
        right_on=["stock_code", "week_end"], how="inner").dropna(subset=["fwd", "target"])
    ics = []
    for _, g in panel.groupby("week_end"):
        if len(g) >= 5 and g["target"].nunique() > 1 and g["fwd"].nunique() > 1:
            ics.append(g["target"].corr(g["fwd"], method="spearman"))
    s = pd.Series(ics).dropna()
    if s.empty:
        return None, None
    icir = float(s.mean() / s.std(ddof=0)) if s.std(ddof=0) > 0 else None
    return (round(float(s.mean()), 4),
            round(float(s.std(ddof=0) / len(s) ** 0.5), 4),
            round(icir, 4) if icir is not None else None)


def _wave(bt, focus, start, end):
    w = bt[(bt["stock_code"] == focus) &
           (bt["week_end"] >= start) & (bt["week_end"] <= end)]
    if w.empty:
        return None, 0
    return round(float((1 + w["pnl"]).prod() - 1), 6), int((w["position"] > 0).sum())


def _capture(bt, weekly_kl):
    """上行/下行捕获：策略周收益 vs 等权买入持有基准"""
    strat = bt.groupby("week_end")["pnl"].mean().rename("strat")
    bench = buy_hold_returns(weekly_kl).rename("mkt")
    j = pd.concat([strat, bench], axis=1).dropna()
    if j.empty:
        return {"upside_capture": None, "downside_capture": None}
    up, dn = j[j["mkt"] > 0], j[j["mkt"] < 0]
    return {
        "upside_capture": round(float(up["strat"].mean() / up["mkt"].mean()), 4)
        if len(up) else None,
        "downside_capture": round(float(dn["strat"].mean() / dn["mkt"].mean()), 4)
        if len(dn) else None,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF 层级消融实验")
    parser.add_argument("--focus", default=None,
                        help="重点观察股票（默认无：universe 级，不输出个股波段列）")
    parser.add_argument("--start", default="2021-01-01")
    parser.add_argument("--end", default=None)
    args = parser.parse_args(argv)

    settings = load_qcfp_settings()
    logger = setup_logger("layer_ablation_test", log_file="layer_ablation_test.log", mode="a")
    logger.info("=== 层级消融实验启动 ===")

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
    wave_start, wave_end = "2024-02-02", "2024-10-31"

    sig_full = build_signal_timeline(structural, monthly, weekly, chip, idx, settings,
                                     weekly_kl=weekly_kl, daily=daily)
    no_ov = copy.deepcopy(settings)
    no_ov["decision"]["tactical_override"]["enabled"] = False
    sig_nov = build_signal_timeline(structural, monthly, weekly, chip, idx, no_ov,
                                    weekly_kl=weekly_kl, daily=daily)

    models = {
        "Q": sig_nov.copy(),
        "QM": sig_nov.copy(),
        "QMW": sig_nov.copy(),
        "Full": sig_full.copy(),
    }
    models["Q"]["target"] = _q_target(models["Q"])
    models["QM"]["target"] = _qm_target(models["QM"])

    rows = []
    for name, sig in models.items():
        bt = run_backtest(sig, weekly_kl, settings, start=args.start, end=end)
        port = portfolio_returns(bt)
        perf = evaluate(port["portfolio_return"], turnover=port["avg_turnover"])
        ic_stats = {h: rank_ic(sig, weekly_kl, horizon=h) for h in (4, 13, 26)}
        wr = wp = None
        if args.focus:
            wr, wp = _wave(bt, args.focus, wave_start, wave_end)
        cap = _capture(bt, weekly_kl)
        row = {
            "model": name,
            "annualized_return": perf.get("annualized_return"),
            "sharpe": perf.get("sharpe"),
            "max_drawdown": perf.get("max_drawdown"),
            "profit_factor": perf.get("profit_factor"),
            "annual_turnover": perf.get("annual_turnover"),
            "avg_weekly_cost": round(float(bt["cost"].mean()), 6),
            "rank_ic_4w": ic_stats[4][0], "rank_ic_13w": ic_stats[13][0],
            "rank_ic_26w": ic_stats[26][0],
            "icir_13w": ic_stats[13][2],
            **cap,
        }
        if args.focus:
            row[f"{args.focus}_wave_return"] = wr
            row[f"{args.focus}_wave_pos_weeks"] = wp
        rows.append(row)
        logger.info(
            f"{name}: 年化 {perf['annualized_return']:.2%}  Sharpe {perf['sharpe']}  "
            f"回撤 {perf['max_drawdown']:.2%}  PF {perf['profit_factor']}  "
            f"换手 {perf['annual_turnover']:.2f}  IC4/13/26 "
            f"{ic_stats[4][0]}/{ic_stats[13][0]}/{ic_stats[26][0]}  ICIR13 {ic_stats[13][2]}  | "
            f"{args.focus} 波段 "
            f"{wr if wr is None else f'{wr:.2%}'}（{wp} 周）  | 上行捕获 "
            f"{cap['upside_capture']} 下行捕获 {cap['downside_capture']}")

    # Full 模型试多专项统计（Recovery/Bottom-Fishing Backtest，P1-3）
    ov_sig = sig_full[sig_full["is_override"]]
    bt_full = run_backtest(sig_full, weekly_kl, settings, start=args.start, end=end)
    ov_bt = bt_full.merge(
        ov_sig[["stock_code", "decision_date"]],
        left_on=["stock_code", "week_end"], right_on=["stock_code", "decision_date"],
        how="inner")
    trial_stats = {
        "n_override_weeks": int(len(ov_sig)),
        "n_override_stocks": int(ov_sig["stock_code"].nunique()),
        "avg_weekly_pnl": round(float(ov_bt["pnl"].mean()), 6)
        if len(ov_bt) else None,
        "avg_override_target": round(float(ov_sig["target"].mean()), 4)
        if len(ov_sig) else None,
    }
    logger.info(f"试多专项（Full）：{trial_stats}")
    for r in rows:
        r["trial"] = trial_stats if r["model"] == "Full" else None

    result = pd.DataFrame(rows)
    report_root = get_report_root() / "backtest"
    report_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    (report_root / f"layer_ablation_{stamp}.json").write_text(
        json.dumps({"generated_at": stamp, "focus": args.focus,
                    "models": rows, "trial_stats": trial_stats},
                   ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    result.to_csv(report_root / f"layer_ablation_{stamp}.csv",
                  index=False, encoding="utf-8-sig")
    logger.info(f"报告已保存: Report/QCFP_MTF/backtest/layer_ablation_{stamp}.{{json,csv}}")
    logger.info("layer_ablation_test 完成 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
