#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF Validation —— 横截面 Top-N 组合回测

每周末按 QCFP 评分选 Top-N，等权（按 Risk 仓位缩放），
对比等权全股票买入持有与恒指基准。

用法：
    python Core/QCFP_MTF/scripts/cross_sectional_backtest.py [--top-n 3,5,10]
        [--start 2021-01-01] [--end 2026-08-14]
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

from QCFP_MTF.backtest.benchmark import (buy_hold_returns, excess_stats,
                                         hsi_returns, momentum_top_n)
from QCFP_MTF.backtest.cross_sectional import cross_sectional_portfolio
from QCFP_MTF.backtest.data_pipeline import build_signal_timeline
from QCFP_MTF.backtest.lookahead_filter import assert_no_lookahead
from QCFP_MTF.backtest.performance import evaluate
from QCFP_MTF.backtest.pit_universe import (filter_by_universe,
                                            filter_price_universe, load_universe)
from QCFP_MTF.common.db import connect
from QCFP_MTF.common.logger import setup_logger
from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.config.settings import load_qcfp_settings
from QCFP_MTF.data.loader import load_derived, load_idx_hist, load_kline


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF 横截面 Top-N 回测")
    parser.add_argument("--top-n", default="3,5,10", help="逗号分隔的持仓数")
    parser.add_argument("--start", default="2021-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument("--require-universe", action="store_true",
                        help="PIT 股票池缺失时报错")
    parser.add_argument("--engine", choices=["legacy", "canonical"],
                        default=None,
                        help="canonical=唯一决策引擎 target（回测与 Live 同源）")
    args = parser.parse_args(argv)

    settings = load_qcfp_settings()
    logger = setup_logger("cross_sectional_backtest",
                          log_file="cross_sectional_backtest.log", mode="a")

    structural = pd.read_sql_query(
        "SELECT stock_code, period_end, available_date, structural_regime, "
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

    signals = build_signal_timeline(structural, monthly, weekly, chip, idx, settings,
                                    weekly_kl=weekly_kl, daily=daily)
    assert_no_lookahead(signals)
    logger.info(f"信号时间线 {len(signals)} 行，Look-ahead 检查通过")
    engine_source = args.engine or settings.get("backtest", {}).get(
        "engine_source", "canonical")
    if engine_source == "canonical":
        from QCFP_MTF.backtest.canonical import canonical_replay
        signals = canonical_replay(signals, settings, run_id="xsec_canonical",
                                   daily=daily)
        logger.info("Canonical Engine 重放：横截面回测使用唯一决策引擎 target")
    else:
        import warnings
        warnings.warn(
            "P0-1 Canonical-only：cross_sectional 使用 legacy（"
            "NON_AUTHORITATIVE / SHADOW_ONLY），非正式研究来源")
    universe = load_universe()
    if not universe.empty:
        signals = filter_by_universe(signals, universe)
        logger.info(f"PIT 股票池过滤后 {len(signals)} 行")
    elif args.require_universe or settings.get("backtest", {}).get("mode", "research") == "production":
        logger.error("正式回测要求 Config/qcfp_universe.csv，缺失禁止产出绩效")
        return 2
    else:
        logger.warning("未配置 qcfp_universe.csv，回退为信号表全部股票（研究模式）")
    min_amount = float(settings.get("backtest", {}).get("liquidity", {})
                       .get("min_weekly_amount", 0.0))

    end = args.end or signals["decision_date"].max()
    bench_kl = filter_price_universe(weekly_kl, universe) if not universe.empty else weekly_kl
    bench_bh = buy_hold_returns(bench_kl)
    bench_hsi = hsi_returns(idx, signals["decision_date"].unique())

    summary = {}
    for top_n in [int(x) for x in args.top_n.split(",") if x.strip()]:
        port = cross_sectional_portfolio(signals, weekly_kl, settings,
                                         top_n=top_n, min_amount=min_amount,
                                         start=args.start, end=end)
        if port.empty:
            continue
        perf = evaluate(port["portfolio_return"], turnover=port["turnover"])
        pr = port.set_index("week_end")["portfolio_return"]
        eb = excess_stats(pr, bench_bh.reindex(pr.index))
        eh = excess_stats(pr, bench_hsi.reindex(pr.index))
        mom = momentum_top_n(bench_kl, top_n=top_n, start=args.start, end=end)
        em = excess_stats(pr, mom.reindex(pr.index))
        summary[f"top{top_n}"] = {"perf": perf, "excess_buy_hold": eb,
                                  "excess_hsi": eh, "excess_momentum": em,
                                  "n_weeks": int(len(port))}
        logger.info(f"=== Top-{top_n} ===")
        logger.info(f"  年化 {perf['annualized_return']:.2%}  Sharpe {perf['sharpe']}  "
                    f"回撤 {perf['max_drawdown']:.2%}  换手 {perf['annual_turnover']:.2f}")
        logger.info(f"  超额(等权基准) {eb.get('excess_annualized'):.2%}  IR {eb.get('information_ratio')}"
                    f"  超额(恒指) {eh.get('excess_annualized'):.2%}  IR {eh.get('information_ratio')}"
                    f"  超额(动量) {em.get('excess_annualized'):.2%}  IR {em.get('information_ratio')}")
        port.to_csv(get_report_root() / "backtest" / f"cross_sectional_top{top_n}.csv",
                    index=False, encoding="utf-8-sig")

    report_root = get_report_root() / "backtest"
    report_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    (report_root / f"cross_sectional_{stamp}.json").write_text(
        json.dumps({"generated_at": stamp, "start": args.start, "end": end,
                    "summary": summary},
                   ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    logger.info(f"横截面回测报告已保存: Report/QCFP_MTF/backtest/cross_sectional_{stamp}.json")
    logger.info("cross_sectional_backtest 完成 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
