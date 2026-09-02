#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF —— 敏感性回测：放宽 C 阈值 × FSM-1 恢复路径

按变体重算季度结构（C/F/P + FSM-1）→ 决策时间线 → 组合回测，
比较基线 vs 各变体，并单独统计指定股票在 2024-02~10 波段内的策略收益。

用法：
    python Core/QCFP_MTF/scripts/sensitivity_backtest.py
        [--focus 01951] [--c-thresholds 0.5,0.3,0.2] [--recoveries 0,1]
        [--start 2021-01-01] [--end 2026-08-21]
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
from QCFP_MTF.backtest.engine import portfolio_returns, run_backtest
from QCFP_MTF.backtest.performance import evaluate
from QCFP_MTF.common.db import connect
from QCFP_MTF.common.logger import setup_logger
from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.config.settings import load_qcfp_settings
from QCFP_MTF.data.loader import load_derived, load_idx_hist, load_kline
from QCFP_MTF.scripts.structural_engine import build_merged
from QCFP_MTF.structural.structural_regime import RECOVERY_STATES, resolve_regime

# 激进恢复路径：额外允许 F 平向但 P 转好的季度退出退潮
AGGRESSIVE_RECOVERY = dict(RECOVERY_STATES)
AGGRESSIVE_RECOVERY.update({
    ("C↑", "F→", "P↑"): "STRUCTURAL_ACCUMULATION",
    ("C→", "F→", "P↑"): "STRUCTURAL_ACCUMULATION",
})


def rebuild_structural(settings, c_thr, recovery_level, lag, stocks=None) -> pd.DataFrame:
    """按变体重算季度结构（与 structural_engine 同输入、同传播逻辑）"""
    ih = load_derived("quarterly_institutional_holdings_analysis")
    chip = load_derived("quarterly_chip_analysis")
    q = load_kline("quarterly", stocks=stocks)
    d = load_kline("daily", stocks=stocks)
    if stocks:
        ih = ih[ih["stock_code"].isin(stocks)]
        chip = chip[chip["stock_code"].isin(stocks)]
    vs = copy.deepcopy(settings)
    vs["structural"]["direction_thresholds"]["c_pp_threshold"] = float(c_thr)
    merged, *_ = build_merged(ih, chip, q, d, vs)
    merged = merged.sort_values(["stock_code", "period_end"]).reset_index(drop=True)

    prev, regimes, methods = {}, [], []
    for _, r in merged.iterrows():
        p = prev.get(r["stock_code"])
        recovery_paths = recovery_level > 0
        rec_map = AGGRESSIVE_RECOVERY if recovery_level >= 2 else None
        rg, m = resolve_regime(r["c_state"], r["f_state"], r["p_state"],
                               p, recovery_paths=recovery_paths,
                               recovery_states=rec_map)
        prev[r["stock_code"]] = rg
        regimes.append(rg)
        methods.append(m)
    merged["structural_regime"] = regimes
    merged["resolve_method"] = methods
    merged["available_date"] = (
        pd.to_datetime(merged["period_end"]) + pd.Timedelta(days=lag)
    ).dt.strftime("%Y-%m-%d")

    dq = pd.read_sql_query(
        "SELECT stock_code, period_end, data_quality FROM qcfp_quarterly_structural",
        connect())
    merged = merged.merge(dq, on=["stock_code", "period_end"], how="left")
    cols = ["stock_code", "stock_name", "period_end", "available_date",
            "structural_regime", "c_state", "f_state", "p_state",
            "q_trend_score", "q_position_52w", "data_quality"]
    return merged[cols]


def _load_pipeline(settings):
    structural_base = None  # 由变体重建
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
    return monthly, weekly, chip, idx, weekly_kl, daily


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF 敏感性回测")
    parser.add_argument("--focus", default="01951", help="重点观察股票（默认 01951）")
    parser.add_argument("--c-thresholds", default="0.5,0.3,0.2",
                        help="C 阈值变体（逗号分隔）")
    parser.add_argument("--recoveries", default="0,1,2",
                        help="恢复路径变体（0=关,1=标准,2=激进，逗号分隔）")
    parser.add_argument("--start", default="2021-01-01")
    parser.add_argument("--end", default=None)
    args = parser.parse_args(argv)

    settings = load_qcfp_settings()
    lag = int(settings.get("institutional", {}).get("disclosure_lag_days", 45))
    logger = setup_logger("sensitivity_backtest",
                          log_file="sensitivity_backtest.log", mode="a")
    logger.info("=== 敏感性回测启动 ===")

    monthly, weekly, chip, idx, weekly_kl, daily = _load_pipeline(settings)
    end = args.end or weekly["week_end"].max()
    c_list = [float(x) for x in args.c_thresholds.split(",") if x.strip()]
    r_list = [int(x) for x in args.recoveries.split(",") if x.strip()]

    # 波段买入持有基准（focus 股票 2024-02~10）
    wave_start, wave_end = "2024-02-02", "2024-10-31"
    wf = weekly_kl[weekly_kl["stock_code"] == args.focus].copy()
    wf["week_end"] = pd.to_datetime(wf["date"]).dt.strftime("%Y-%m-%d")
    wf = wf.sort_values("week_end")
    wf["ret"] = wf.groupby("stock_code")["close"].pct_change()
    wave_bh = (1 + wf[(wf["week_end"] >= wave_start) & (wf["week_end"] <= wave_end)]
               ["ret"].fillna(0)).prod() - 1
    logger.info(f"{args.focus} 波段买入持有（{wave_start}~{wave_end}）: {wave_bh:.2%}")

    variants = []
    for c_thr in c_list:
        for recovery in r_list:
            label = f"C{c_thr:.1f}" + ({0: "", 1: "+RECOVERY", 2: "+RECOVERY2"}[recovery])
            structural = rebuild_structural(settings, c_thr, recovery, lag)
            signals = build_signal_timeline(structural, monthly, weekly, chip,
                                            idx, settings,
                                            weekly_kl=weekly_kl, daily=daily)
            bt = run_backtest(signals, weekly_kl, settings,
                              start=args.start, end=end)
            port = portfolio_returns(bt)
            perf = evaluate(port["portfolio_return"], turnover=port["avg_turnover"])

            wave = bt[(bt["stock_code"] == args.focus) &
                      (bt["week_end"] >= wave_start) &
                      (bt["week_end"] <= wave_end)] if args.focus else None
            wave_ret = float((1 + wave["pnl"]).prod() - 1) \
                if wave is not None and len(wave) else None
            wave_pos_weeks = int((wave["position"] > 0).sum()) \
                if wave is not None else 0
            wave_n = len(wave) if wave is not None else 0

            variants.append({
                "variant": label,
                "c_threshold": c_thr,
                "recovery": recovery,
                "annualized_return": perf.get("annualized_return"),
                "sharpe": perf.get("sharpe"),
                "max_drawdown": perf.get("max_drawdown"),
                "annual_turnover": perf.get("annual_turnover"),
                f"{args.focus}_wave_return": round(wave_ret, 6) if wave_ret is not None else None,
                f"{args.focus}_wave_pos_weeks": wave_pos_weeks,
                f"{args.focus}_wave_weeks": wave_n,
            })
            wave_str = f"{wave_ret:.2%}" if wave_ret is not None else "—"
            logger.info(
                f"{label}: 组合年化 {perf['annualized_return']:.2%}  "
                f"Sharpe {perf['sharpe']}  回撤 {perf['max_drawdown']:.2%}  | "
                f"{args.focus} 波段收益 {wave_str} "
                f"（持仓 {wave_pos_weeks}/{wave_n} 周）")

    result = pd.DataFrame(variants)
    report_root = get_report_root() / "backtest"
    report_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    (report_root / f"sensitivity_{stamp}.json").write_text(
        json.dumps({"generated_at": stamp, "focus": args.focus,
                    "wave": {"start": wave_start, "end": wave_end,
                             "buy_hold": wave_bh},
                    "variants": result.to_dict(orient="records")},
                   ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    result.to_csv(report_root / f"sensitivity_{stamp}.csv",
                  index=False, encoding="utf-8-sig")
    logger.info(f"敏感性报告已保存: Report/QCFP_MTF/backtest/sensitivity_{stamp}.{{json,csv}}")
    logger.info("sensitivity_backtest 完成 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
