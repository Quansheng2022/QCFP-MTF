#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF 2.3 —— Wave Capture Report（波段捕获指标）

回答"散户波段系统到底有没有捕捉中短期大波段"，而不是只看 Sharpe：
    Wave Capture Ratio / Entry Delay / MFE / MAE / Peak Capture /
    Missed Wave Rate / False Entry Rate

用法：
    python Core/QCFP_MTF/scripts/wave_capture_report.py
        [--stock 01951] [--min-gain 0.5] [--window 26] [--year 2024]
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

from QCFP_MTF.backtest.data_pipeline import build_signal_timeline
from QCFP_MTF.backtest.engine import run_backtest
from QCFP_MTF.backtest.performance import evaluate as evaluate_perf
from QCFP_MTF.backtest.retail_utility import (false_participation_rate,
                                              false_exit_rate,
                                              opportunity_cost,
                                              retail_utility_score,
                                              risk_budget_efficiency,
                                              time_in_position, whipsaw_rate)
from QCFP_MTF.backtest.wave_capture import (false_entry_rate, find_waves,
                                            wave_capture_metrics,
                                            wave_capture_summary)
from QCFP_MTF.common.db import connect
from QCFP_MTF.common.logger import setup_logger
from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.config.settings import load_qcfp_settings
from QCFP_MTF.data.loader import load_derived, load_idx_hist, load_kline


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF Wave Capture Report")
    parser.add_argument("--stock", default=None)
    parser.add_argument("--min-gain", type=float, default=0.5)
    parser.add_argument("--window", type=int, default=26)
    parser.add_argument("--year", type=int, default=None)
    args = parser.parse_args(argv)
    settings = load_qcfp_settings()
    logger = setup_logger("wave_capture_report",
                          log_file="wave_capture_report.log", mode="a")
    logger.info("=== Wave Capture Report 启动 ===")

    conn = connect()
    try:
        structural = pd.read_sql_query(
            "SELECT * FROM qcfp_quarterly_structural", conn)
        monthly = pd.read_sql_query(
            "SELECT * FROM qcfp_monthly_behavior", conn)
        weekly = pd.read_sql_query(
            "SELECT * FROM qcfp_weekly_tactical", conn)
        daily = pd.read_sql_query(
            "SELECT * FROM qcfp_daily_tactical", conn)
    finally:
        conn.close()
    chip = load_derived("quarterly_chip_analysis")[["stock_code",
                                                    "quarter_end_date",
                                                    "chip_structure_score"]]
    idx = load_idx_hist()
    weekly_kl = load_kline("weekly")

    stocks = [args.stock] if args.stock else None
    signals = build_signal_timeline(structural, monthly, weekly, chip, idx,
                                    settings, stocks=stocks,
                                    weekly_kl=weekly_kl, daily=daily)
    if signals.empty:
        logger.error("无可回测信号")
        return 1
    bt = run_backtest(signals, weekly_kl, settings)
    waves = find_waves(weekly_kl, min_gain=args.min_gain,
                       window=args.window)
    if args.year:
        waves = waves[waves["start_date"].str.startswith(str(args.year))]
    if args.stock:
        waves = waves[waves["stock_code"] == args.stock]
    metrics = wave_capture_metrics(bt, waves)
    summary = wave_capture_summary(metrics)
    summary["false_entry_rate"] = false_entry_rate(bt, waves)
    port = bt.groupby("week_end")["pnl"].mean()
    perf = evaluate_perf(port, turnover=bt.groupby("week_end")["turnover"].mean())
    avg_exp = float(bt["position_start"].mean())
    utility = retail_utility_score(
        perf.get("annualized_return"), avg_exp,
        summary.get("capture_ratio_mean"), perf.get("profit_factor"),
        perf.get("max_drawdown"), perf.get("annual_turnover"))
    utility["opportunity_miss_rate"] = summary.get("missed_wave_rate")
    utility["false_participation_rate"] = false_participation_rate(metrics)
    utility["opportunity_cost"] = opportunity_cost(metrics)
    utility["risk_budget_efficiency"] = risk_budget_efficiency(
        perf.get("annualized_return"), perf.get("max_drawdown"), avg_exp)
    utility["time_in_position"] = time_in_position(bt)
    utility["avg_exposure"] = round(avg_exp, 4)
    utility["false_exit_rate"] = false_exit_rate(bt, weekly_kl)
    utility["whipsaw_rate"] = whipsaw_rate(bt)
    summary["retail_utility"] = utility
    summary["min_gain"] = args.min_gain
    summary["window_weeks"] = args.window
    if args.year:
        summary["year"] = args.year

    logger.info(
        f"波段 {summary['n_waves']} 个（≥{args.min_gain:.0%}，"
        f"{args.window} 周窗口）")
    logger.info(
        f"  捕获 {summary.get('participated')} 个，错失率 "
        f"{summary.get('missed_wave_rate')}，捕获比 "
        f"{summary.get('capture_ratio_mean')}，进入延迟 "
        f"{summary.get('entry_delay_mean_weeks')} 周")
    logger.info(f"  MFE {summary.get('mfe_mean')} / MAE "
                f"{summary.get('mae_mean')} / 错误试仓率 "
                f"{summary.get('false_entry_rate')} / 牛散效用 "
                f"{utility['retail_utility_score']}")

    out_dir = get_report_root() / "wave_capture"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    focus = args.stock or "all"
    base = f"wave_capture_{focus}_{stamp}"
    if args.year:
        base += f"_{args.year}"
    metrics.to_csv(out_dir / f"{base}.csv", index=False,
                   encoding="utf-8-sig")
    (out_dir / f"{base}.json").write_text(
        json.dumps({"generated_at": stamp, "summary": summary,
                    "waves": metrics.to_dict(orient="records")},
                   ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")
    lines = ["# QCFP-MTF Wave Capture Report\n",
             f"- 生成时间：{stamp}　焦点：{args.stock or '全部'}　"
             f"min_gain≥{args.min_gain:.0%}　窗口 {args.window} 周"
             + (f"　年度：{args.year}" if args.year else "") + "\n",
             "## 汇总\n",
             "| 指标 | 值 |", "| :-- | :-- |",
             f"| 波段数 | {summary['n_waves']} |",
             f"| 参与波段 | {summary.get('participated')} |",
             f"| 错失率 | {summary.get('missed_wave_rate')} |",
             f"| 捕获比均值 | {summary.get('capture_ratio_mean')} |",
             f"| 进入延迟（周） | {summary.get('entry_delay_mean_weeks')} |",
             f"| MFE 均值 | {summary.get('mfe_mean')} |",
             f"| MAE 均值 | {summary.get('mae_mean')} |",
             f"| 错误试仓率 | {summary.get('false_entry_rate')} |\n"]
    lines += ["## 牛散效用（Retail Utility）\n",
              "### A. 波段能力\n",
              f"- Wave Capture：{utility.get('opportunity_miss_rate')}（错失率）\n",
              "### B. 风险纪律\n",
              f"- 错误参与率：{utility.get('false_participation_rate')}｜"
              f"错误退出率：{utility.get('false_exit_rate')}｜"
              f"波段噪声率：{utility.get('whipsaw_rate')}｜"
              f"风险预算效率：{utility.get('risk_budget_efficiency')}\n",
              "### C. 资金效率\n",
              f"- 资金效率：{utility.get('capital_efficiency')}｜"
              f"平均暴露：{utility.get('avg_exposure')}｜"
              f"持仓时间占比：{utility.get('time_in_position')}\n",
              "### Opportunity Cost（被过滤波段的平均少赚）\n",
              f"- {utility.get('opportunity_cost')}\n",
              "> 效用评分为展示指标（不用于校准）："
              f"{utility['retail_utility_score']}\n"]
    if not metrics.empty:
        lines += ["## 波段明细\n",
                  "| 股票 | 起始 | 峰值 | 波段收益 | 策略收益 | 捕获比 | "
                  "进入延迟 | MFE | MAE | 参与 |", "| :-- | :-- | :-- | "
                  "--: | --: | --: | --: | --: | --: | :-- |"]
        for _, r in metrics.iterrows():
            sr = (f"{r['strategy_return']:.1%}"
                  if r["strategy_return"] is not None else "—")
            lines.append(
                f"| {r['stock_code']} | {r['start_date']} | {r['peak_date']} "
                f"| {r['gain']:.1%} | {sr} | "
                f"{r['capture_ratio']} | "
                f"{r['entry_delay_weeks']} | {r['mfe']:.1%} | "
                f"{r['mae']:.1%} | {'✓' if r['participated'] else '✗'} |")
    (out_dir / f"{base}.md").write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"报告已保存: Report/QCFP_MTF/wave_capture/{base}.{{md,csv,json}}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
