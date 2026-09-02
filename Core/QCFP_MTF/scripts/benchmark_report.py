#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF 2.7 —— Benchmark Report（固定基准体系 B0–B7）

回答"QCFP_MTF 是否真的比简单方法更有价值"：
    Return / MDD / Sharpe / Calmar / Wave Capture / False Entry / Turnover /
    Capital Efficiency + 相对 B0/B1 的风险调整增量效用。

用法：python Core/QCFP_MTF/scripts/benchmark_report.py [--stock 01951]
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

from QCFP_MTF.backtest.benchmarks import (benchmark_targets,
                                          risk_adjusted_incremental)
from QCFP_MTF.backtest.data_pipeline import build_signal_timeline
from QCFP_MTF.backtest.engine import portfolio_returns, run_backtest
from QCFP_MTF.backtest.performance import evaluate as evaluate_perf
from QCFP_MTF.backtest.wave_capture import (find_waves, wave_capture_metrics,
                                            wave_capture_summary)
from QCFP_MTF.common.db import connect
from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.config.settings import load_qcfp_settings
from QCFP_MTF.data.loader import load_derived, load_idx_hist, load_kline


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF Benchmark Report")
    parser.add_argument("--stock", default=None)
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
    from QCFP_MTF.backtest.canonical import canonical_replay
    bench = benchmark_targets(signals, weekly_kl, settings)
    bench["B7_FullQCFPMTF"] = canonical_replay(
        signals, settings, run_id="bench_full", daily=daily)
    waves = find_waves(weekly_kl, min_gain=0.5, window=26)
    if args.stock:
        waves = waves[waves["stock_code"] == args.stock]
    rows = []
    for name, s in bench.items():
        bt = run_backtest(s, weekly_kl, settings)
        port = portfolio_returns(bt)
        perf = evaluate_perf(port["portfolio_return"],
                             turnover=port["avg_turnover"])
        ws = wave_capture_summary(wave_capture_metrics(bt, waves))
        avg_exp = float(bt["position_start"].mean())
        cap_eff = perf.get("annualized_return") / avg_exp \
            if avg_exp > 0 else None
        rows.append({
            "benchmark": name,
            "annualized_return": perf.get("annualized_return"),
            "sharpe": perf.get("sharpe"),
            "max_drawdown": perf.get("max_drawdown"),
            "calmar": perf.get("calmar"),
            "annual_turnover": perf.get("annual_turnover"),
            "wave_capture": ws.get("capture_ratio_mean"),
            "false_entry": ws.get("false_entry_rate"),
            "capital_efficiency": round(cap_eff, 4) if cap_eff is not None
            else None,
        })
    base = next((r for r in rows if r["benchmark"] == "B0_BuyHold"), None)
    for r in rows:
        r["incremental_utility_vs_B0"] = risk_adjusted_incremental(
            base["annualized_return"] if base else None, r["annualized_return"],
            base["max_drawdown"] if base else None, r["max_drawdown"])
    out_dir = get_report_root() / "benchmark"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    focus = args.stock or "all"
    base_f = f"benchmark_{focus}_{stamp}"
    (out_dir / f"{base_f}.json").write_text(
        json.dumps({"generated_at": stamp, "rows": rows},
                   ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")
    md = ["# QCFP-MTF Benchmark Report\n",
          f"- 焦点：{args.stock or '全部'}　时间：{stamp}\n",
          "| 基准 | 年化 | Sharpe | MDD | Calmar | 换手 | 波段捕获 | 错误试仓 | 资金效率 | 增量效用 vs B0 |",
          "| :-- | --: | --: | --: | --: | --: | --: | --: | --: | --: |"]
    for r in rows:
        md.append(
            f"| {r['benchmark']} | {r['annualized_return']:.2%} | "
            f"{r['sharpe']} | {r['max_drawdown']:.2%} | {r['calmar']} | "
            f"{r['annual_turnover']:.2f} | {r['wave_capture']} | "
            f"{r['false_entry']} | {r['capital_efficiency']} | "
            f"{r['incremental_utility_vs_B0']} |")
    (out_dir / f"{base_f}.md").write_text("\n".join(md), encoding="utf-8")
    print(f"Benchmark Report 已保存: {base_f}.{{md,json}}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
