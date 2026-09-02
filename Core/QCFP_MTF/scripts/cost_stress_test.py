#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF —— 成本压力测试（Cost Stress / Capacity Sensitivity，P1）

对同一信号时间线在 0.5x / 1x / 2x / 3x / 4x 交易成本乘数下重跑组合回测，
对比 Sharpe/MDD/收益——评估策略对成本/流动性压力的敏感性。
（ADV/参与率的完整流动性模型留待数据接入后扩展。）

用法：
    python Core/QCFP_MTF/scripts/cost_stress_test.py [--factors 0.5,1,2,3,4]
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

from QCFP_MTF.backtest.canonical_runs import run_canonical_stress
from QCFP_MTF.backtest.engine import portfolio_returns
from QCFP_MTF.backtest.performance import evaluate
from QCFP_MTF.common.db import connect
from QCFP_MTF.common.logger import setup_logger
from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.config.settings import load_qcfp_settings
from QCFP_MTF.data.loader import load_derived, load_idx_hist, load_kline


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF 成本压力测试")
    parser.add_argument("--factors", default="0.5,1,2,3,4")
    parser.add_argument("--start", default="2021-01-01")
    parser.add_argument("--end", default=None)
    args = parser.parse_args(argv)

    settings = load_qcfp_settings()
    logger = setup_logger("cost_stress_test", log_file="cost_stress_test.log", mode="a")
    logger.info("=== 成本压力测试启动 ===")

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
    # PWC-1（第 8 项）：Formal Stress 必须 Canonical-Only——
    # 只允许 run_canonical_stress（evidence → canonical_replay → run_backtest）。

    rows = []
    for f in [float(x) for x in args.factors.split(",") if x.strip()]:
        s = copy.deepcopy(settings)
        for sec in ("commission_rate", "stamp_rate", "slippage_rate", "levy_rate"):
            if sec in s.get("backtest", {}).get("cost", {}):
                s["backtest"]["cost"][sec] = float(s["backtest"]["cost"][sec]) * f
        bt = run_canonical_stress(
            structural, monthly, weekly, chip, idx, s,
            stress_settings=[{"label": f"cost{f}",
                              "settings": s}],
            weekly_kl=weekly_kl, daily=daily,
            run_id=f"cost_stress_{f}")["scenarios"][
                f"cost{f}"]["backtest"]
        port = portfolio_returns(bt)
        perf = evaluate(port["portfolio_return"], turnover=port["avg_turnover"])
        rows.append({
            "cost_factor": f,
            "annualized_return": perf.get("annualized_return"),
            "sharpe": perf.get("sharpe"),
            "max_drawdown": perf.get("max_drawdown"),
            "profit_factor": perf.get("profit_factor"),
            "annual_turnover": perf.get("annual_turnover"),
            "annual_cost": round(float(bt["cost"].mean() * 52), 6),
        })
        logger.info(
            f"cost×{f}: 年化 {perf['annualized_return']:.2%}  Sharpe {perf['sharpe']}  "
            f"回撤 {perf['max_drawdown']:.2%}  PF {perf['profit_factor']}  "
            f"换手 {perf['annual_turnover']:.2f}  年化成本 {rows[-1]['annual_cost']:.2%}")

    result = pd.DataFrame(rows)
    report_root = get_report_root() / "backtest"
    report_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    (report_root / f"cost_stress_{stamp}.json").write_text(
        json.dumps({"generated_at": stamp, "models": result.to_dict(orient="records")},
                   ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    result.to_csv(report_root / f"cost_stress_{stamp}.csv",
                  index=False, encoding="utf-8-sig")
    logger.info(f"报告已保存: Report/QCFP_MTF/backtest/cost_stress_{stamp}.{{json,csv}}")
    logger.info("cost_stress_test 完成 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
