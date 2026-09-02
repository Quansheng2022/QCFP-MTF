#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF Validation —— 增量信息价值实验（Model 0~6）

依次验证：P only → C+P → C+F+P → +Monthly → +Weekly → 完整 MTF
在横截面 Top-N 框架下比较年化/Sharpe/回撤/超额（相对等权全池）。

用法：
    python Core/QCFP_MTF/scripts/incremental_alpha_test.py [--top-n 5]
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

from QCFP_MTF.backtest.benchmark import buy_hold_returns, excess_stats
from QCFP_MTF.backtest.cross_sectional import cross_sectional_portfolio
from QCFP_MTF.backtest.data_pipeline import build_signal_timeline
from QCFP_MTF.backtest.lookahead_filter import assert_no_lookahead
from QCFP_MTF.backtest.performance import evaluate
from QCFP_MTF.common.db import connect
from QCFP_MTF.common.logger import setup_logger
from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.config.settings import load_qcfp_settings
from QCFP_MTF.data.loader import load_derived, load_idx_hist, load_kline

STATE_SCORE = {"↑": 1.0, "→": 0.0, "↓": -1.0, None: 0.0}
STAGE_SCORE = {"Improving": 1.0, "Stable": 0.0, "Deteriorating": -1.0, None: 0.0}
TRIGGER_SCORE = {"Breakout": 1.0, "Pullback": 0.0,
                 "Consolidation": 0.0, "Breakdown": -1.0, None: 0.0}


def _score(s: pd.Series, mapping) -> pd.Series:
    return s.map(lambda x: mapping.get(x, mapping.get(None, 0.0)))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF 增量信息实验")
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument("--start", default="2021-01-01")
    args = parser.parse_args(argv)

    settings = load_qcfp_settings()
    logger = setup_logger("incremental_alpha_test",
                          log_file="incremental_alpha_test.log", mode="a")

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
    bench_bh = buy_hold_returns(weekly_kl)

    signals["c_s"] = _score(signals["c_state"], STATE_SCORE)
    signals["f_s"] = _score(signals["f_state"], STATE_SCORE)
    signals["p_s"] = _score(signals["p_state"], STATE_SCORE)
    signals["m_s"] = _score(signals["monthly_behavior_state"], STAGE_SCORE)
    signals["w_s"] = _score(signals["tactical_signal"], TRIGGER_SCORE)

    models = {
        "M1_C": signals["c_s"],
        "M2_F": signals["f_s"],
        "M3_P": signals["p_s"],
        "M4_CF": signals["c_s"] + signals["f_s"],
        "M5_CP": signals["c_s"] + signals["p_s"],
        "M6_FP": signals["f_s"] + signals["p_s"],
        "M7_CFP": signals["c_s"] + signals["f_s"] + signals["p_s"],
        "M8_CFP_Monthly": signals["c_s"] + signals["f_s"] + signals["p_s"] + signals["m_s"],
        "M9_CFP_Monthly_Weekly":
            signals["c_s"] + signals["f_s"] + signals["p_s"] + signals["m_s"] + signals["w_s"],
        "M10_Full_MTF": signals["qcfp_score"],
    }

    # M0：等权买入持有基准（Model -1/0 基准，无选股）
    bench_series = bench_bh[bench_bh.index >= args.start]
    rows = [{"model": "M0_BuyHold", **evaluate(bench_series),
             "excess_annualized": 0.0, "information_ratio": None}]
    for name, score in models.items():
        s = signals.copy()
        s["model_score"] = score
        port = cross_sectional_portfolio(s, weekly_kl, settings,
                                         top_n=args.top_n, score_col="model_score",
                                         start=args.start)
        if port.empty:
            rows.append({"model": name, "error": "empty"})
            continue
        perf = evaluate(port["portfolio_return"], turnover=port["turnover"])
        pr = port.set_index("week_end")["portfolio_return"]
        eb = excess_stats(pr, bench_bh.reindex(pr.index))
        rows.append({"model": name, **perf,
                     "excess_annualized": eb.get("excess_annualized"),
                     "information_ratio": eb.get("information_ratio")})
        logger.info(f"{name}: 年化 {perf['annualized_return']:.2%}  "
                    f"Sharpe {perf['sharpe']}  回撤 {perf['max_drawdown']:.2%}  "
                    f"超额 {eb.get('excess_annualized'):.2%}  IR {eb.get('information_ratio')}")

    result = pd.DataFrame(rows)
    report_root = get_report_root() / "backtest"
    report_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    (report_root / f"incremental_alpha_{stamp}.json").write_text(
        json.dumps({"generated_at": stamp, "top_n": args.top_n,
                    "models": result.to_dict(orient="records")},
                   ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    logger.info(f"增量实验报告已保存: Report/QCFP_MTF/backtest/incremental_alpha_{stamp}.json")
    logger.info("incremental_alpha_test 完成 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
