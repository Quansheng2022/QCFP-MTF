#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF 2.6 —— Retail Swing Report（牛散模式逐笔波段报告）

把逐周 PnL 升级为"每笔 Swing Trade"：
    Trade Ledger（entry/exit/加减仓/MFE/MAE/持有周/后验归因）
    + Retail Utility 三维（Opportunity / Risk Discipline / Capital）

用法：python Core/QCFP_MTF/scripts/retail_swing_report.py
        [--stock 01951] [--engine legacy|canonical]
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

from QCFP_MTF.backtest.engine import portfolio_returns, run_backtest
from QCFP_MTF.backtest.data_pipeline import build_signal_timeline
from QCFP_MTF.backtest.performance import evaluate as evaluate_perf
from QCFP_MTF.backtest.retail_utility import (false_exit_rate, opportunity_cost,
                                              risk_budget_efficiency,
                                              time_in_position, whipsaw_rate)
from QCFP_MTF.backtest.trade_ledger import (build_trade_ledger,
                                            trade_ledger_summary)
from QCFP_MTF.backtest.wave_capture import (find_waves, wave_capture_metrics,
                                            wave_capture_summary)
from QCFP_MTF.common.db import connect
from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.config.settings import load_qcfp_settings
from QCFP_MTF.data.loader import load_derived, load_idx_hist, load_kline


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF Retail Swing Report")
    parser.add_argument("--stock", default=None)
    parser.add_argument("--engine", choices=["legacy", "canonical"],
                        default="canonical")
    parser.add_argument("--min-gain", type=float, default=0.5)
    args = parser.parse_args(argv)
    settings = load_qcfp_settings()
    conn = connect()
    try:
        structural = pd.read_sql_query("SELECT * FROM qcfp_quarterly_structural", conn)
        monthly = pd.read_sql_query("SELECT * FROM qcfp_monthly_behavior", conn)
        weekly = pd.read_sql_query("SELECT * FROM qcfp_weekly_tactical", conn)
        daily = pd.read_sql_query("SELECT * FROM qcfp_daily_tactical", conn)
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
        print("❌ 无可回测信号")
        return 1
    if args.engine == "canonical":
        from QCFP_MTF.backtest.canonical import canonical_replay
        signals = canonical_replay(signals, settings, run_id="retail_swing",
                                   daily=daily)
    bt = run_backtest(signals, weekly_kl, settings)
    trades = build_trade_ledger(bt, weekly_kl)
    summary = trade_ledger_summary(trades)
    port = portfolio_returns(bt)
    perf = evaluate_perf(port["portfolio_return"],
                         turnover=port["avg_turnover"])
    avg_exp = float(bt["position_start"].mean())
    waves = find_waves(weekly_kl, min_gain=args.min_gain, window=26)
    if args.stock:
        waves = waves[waves["stock_code"] == args.stock]
    ws = wave_capture_summary(wave_capture_metrics(bt, waves))
    summary["utility"] = {
        "opportunity_capture": ws.get("capture_ratio_mean"),
        "missed_wave_rate": ws.get("missed_wave_rate"),
        "opportunity_cost": opportunity_cost(wave_capture_metrics(bt, waves)),
        "false_exit_rate": false_exit_rate(bt, weekly_kl),
        "whipsaw_rate": whipsaw_rate(bt),
        "time_in_position": time_in_position(bt),
        "risk_budget_efficiency": risk_budget_efficiency(
            perf.get("annualized_return"), perf.get("max_drawdown"), avg_exp),
    }
    out_dir = get_report_root() / "retail_swing"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    focus = args.stock or "all"
    base = f"retail_swing_{focus}_{stamp}"
    trades.to_csv(out_dir / f"{base}.csv", index=False, encoding="utf-8-sig")
    (out_dir / f"{base}.json").write_text(
        json.dumps({"generated_at": stamp, "engine": args.engine,
                    "summary": summary,
                    "trades": trades.to_dict(orient="records")},
                   ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")
    md = ["# QCFP-MTF Retail Swing Report\n",
          f"- 引擎：{args.engine}　焦点：{args.stock or '全部'}\n",
          "## Trade Ledger 汇总\n",
          "| 指标 | 值 |", "| :-- | :-- |"]
    for k, v in summary.items():
        if k != "utility":
            md.append(f"| {k} | {v} |")
    md += ["\n## 逐笔交易\n",
           "| trade | 股票 | 进入 | 退出 | 初始仓 | 最大仓 | +/− | 毛收益 | "
           "MFE | MAE | 持有周 | Entry晚 | Exit早 | Exit晚 |",
           "| :-- | :-- | :-- | :-- | --: | --: | :-- | --: | --: | --: | "
           "--: | :-- | :-- | :-- |"]
    for _, t in trades.head(200).iterrows():
        gr = (f"{t['gross_return']:.1%}"
              if t["gross_return"] is not None else "—")
        md.append(
            f"| {t['trade_id']} | {t['stock_code']} | {t['entry_date']} | "
            f"{t['exit_date']} | {t['initial_position']:.0%} | "
            f"{t['max_position']:.0%} | {t['add_count']}/{t['reduce_count']} | "
            f"{gr} | "
            f"{t['mfe']:.1%} | {t['mae']:.1%} | {t['holding_weeks']} | "
            f"{'✓' if t['entry_late'] else ''} | "
            f"{'✓' if t['exit_early'] else ''} | "
            f"{'✓' if t['exit_late'] else ''} |")
    (out_dir / f"{base}.md").write_text("\n".join(md), encoding="utf-8")
    print(f"Retail Swing Report 已保存: Report/QCFP_MTF/retail_swing/{base}.{{md,csv,json}}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
