#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF Validation Hardening —— 因子/状态信息量分析

验证 C/F/P/CBI 因子与 Structural/MTF 状态的前向收益分层能力：
- 因子 Rank IC（4/13/26 周）
- 状态前向收益表（均值/中位数/命中率）

用法：
    python Core/QCFP_MTF/scripts/ic_analysis.py [--stock 00700] [--start 2021-01-01]
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

from QCFP_MTF.backtest.information_analysis import (conditional_regression,
                                                    factor_rank_ic,
                                                    forward_returns,
                                                    ic_summary,
                                                    state_forward_table,
                                                    cfp_return_matrix)
from QCFP_MTF.common.asof import asof_join_latest
from QCFP_MTF.common.db import connect
from QCFP_MTF.common.logger import setup_logger
from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.config.settings import load_qcfp_settings
from QCFP_MTF.data.loader import load_kline

def _state_score(x):
    if x is None:
        return 0.0
    if str(x).endswith("↑"):
        return 1.0
    if str(x).endswith("↓"):
        return -1.0
    return 0.0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF 因子/状态 IC 分析")
    parser.add_argument("--stock", help="只分析指定股票")
    parser.add_argument("--start", default="2021-01-01", help="起始周（默认 2021-01-01）")
    parser.add_argument("--horizons", default="4,13,26", help="前向窗口（周）")
    args = parser.parse_args(argv)

    settings = load_qcfp_settings()
    lag = int(settings.get("institutional", {}).get("disclosure_lag_days", 45))
    horizons = tuple(int(h) for h in args.horizons.split(","))
    log_name = f"ic_analysis_{args.stock}" if args.stock else "ic_analysis"
    logger = setup_logger("ic_analysis", log_file=f"{log_name}.log", mode="w")
    logger.info(f"=== IC 分析启动（horizons={horizons}）===")

    structural = pd.read_sql_query(
        "SELECT stock_code, period_end, available_date, structural_regime, "
        "c_state, f_state, p_state, inst_ownership_pct_chg, q_inst_flow_z, "
        "q_return FROM qcfp_quarterly_structural",
        connect())
    monthly = pd.read_sql_query(
        "SELECT stock_code, month_end, cbi_score FROM qcfp_monthly_behavior", connect())
    mtf = pd.read_sql_query(
        "SELECT stock_code, decision_date, mtf_regime FROM qcfp_mtf_decision", connect())
    weekly_kl = load_kline("weekly")
    if args.stock:
        structural = structural[structural["stock_code"] == args.stock]
        monthly = monthly[monthly["stock_code"] == args.stock]
        mtf = mtf[mtf["stock_code"] == args.stock]
        weekly_kl = weekly_kl[weekly_kl["stock_code"] == args.stock]

    fwd = forward_returns(weekly_kl, horizons)
    fwd = fwd[fwd["week_end"] >= args.start]

    structural["available_date_dt"] = pd.to_datetime(
        structural["available_date"], errors="coerce")
    structural["available_date_dt"] = structural["available_date_dt"].fillna(
        pd.to_datetime(structural["period_end"], errors="coerce")
        + pd.Timedelta(days=lag))
    monthly["month_end_dt"] = pd.to_datetime(monthly["month_end"], errors="coerce")
    mtf["decision_dt"] = pd.to_datetime(mtf["decision_date"], errors="coerce")

    grid = fwd[["stock_code", "week_end"]].copy()
    grid["decision_dt"] = pd.to_datetime(grid["week_end"], errors="coerce")
    panel = asof_join_latest(
        grid, structural, "decision_dt", "available_date_dt",
        right_cols=["structural_regime", "c_state", "f_state", "p_state",
                    "inst_ownership_pct_chg",
                    "q_inst_flow_z", "q_return"], suffixes=("", "_q"))
    panel = asof_join_latest(
        panel, monthly, "decision_dt", "month_end_dt",
        right_cols=["cbi_score"], suffixes=("", "_m"))
    panel = asof_join_latest(
        panel, mtf, "decision_dt", "decision_dt",
        right_cols=["mtf_regime"], suffixes=("", "_t"))
    panel = panel.merge(fwd, on=["stock_code", "week_end"], how="left")
    panel["c_s"] = panel["c_state"].map(_state_score)
    panel["f_s"] = panel["f_state"].map(_state_score)
    panel["p_s"] = panel["p_state"].map(_state_score)

    factors = {"inst_ownership_pct_chg": "C 因子(机构持股环比)",
               "q_inst_flow_z": "F 因子(资金Z)",
               "q_return": "P 因子(季度收益)",
               "cbi_score": "CBI(行为代理)"}
    ic_report = {}
    logger.info("=== 因子 Rank IC ===")
    for col, name in factors.items():
        ic_report[name] = {}
        for h in horizons:
            ics = factor_rank_ic(panel, col, f"fwd_{h}w")
            summ = ic_summary(ics["ic"])
            ic_report[name][f"fwd_{h}w"] = summ
            logger.info(f"  {name} fwd_{h}w: meanIC={summ['mean_ic']} "
                        f"ICIR={summ['icir']} pos%={summ['positive_ratio']} (n={summ['n']})")

    state_report = {}
    logger.info("=== 状态前向收益 ===")
    for state_col, state_name in [("structural_regime", "结构状态"),
                                  ("mtf_regime", "MTF 状态")]:
        state_report[state_name] = {}
        for h in horizons:
            tbl = state_forward_table(panel, state_col, f"fwd_{h}w")
            state_report[state_name][f"fwd_{h}w"] = tbl.reset_index().to_dict(orient="records")
            if not tbl.empty:
                top = tbl.index[0]
                bottom = tbl.index[-1]
                logger.info(f"  {state_name} fwd_{h}w: 最高均值={top}({tbl.iloc[0]['mean_fwd']:.2%}) "
                            f"最低={bottom}({tbl.iloc[-1]['mean_fwd']:.2%}) "
                            f"spread={tbl.iloc[0]['mean_fwd'] - tbl.iloc[-1]['mean_fwd']:.2%}")

    matrix_report = {}
    logger.info("=== C×F×P 三维收益矩阵（均值）===")
    matrix = cfp_return_matrix(panel, horizons)
    for h in horizons:
        sub = matrix[matrix["horizon"] == f"fwd_{h}w"].copy()
        sub = sub.sort_values("mean_fwd", ascending=False)
        matrix_report[f"fwd_{h}w"] = sub.reset_index().to_dict(orient="records")
        if not sub.empty:
            logger.info(f"  fwd_{h}w 最高：{sub.iloc[0]['c_state']}{sub.iloc[0]['f_state']}"
                        f"{sub.iloc[0]['p_state']}（均值 {sub.iloc[0]['mean_fwd']:.2%}，"
                        f"n={sub.iloc[0]['n']}，t={sub.iloc[0]['t_stat']}）")
            logger.info(f"  fwd_{h}w 最低：{sub.iloc[-1]['c_state']}{sub.iloc[-1]['f_state']}"
                        f"{sub.iloc[-1]['p_state']}（均值 {sub.iloc[-1]['mean_fwd']:.2%}，"
                        f"n={sub.iloc[-1]['n']}，t={sub.iloc[-1]['t_stat']}）")

    cond_report = {}
    logger.info("=== 条件回归（控制 P 后 C/F 的增量解释力）===")
    for h in horizons:
        cond_report[f"fwd_{h}w"] = conditional_regression(panel, f"fwd_{h}w")
        c = cond_report[f"fwd_{h}w"]
        logger.info(f"  fwd_{h}w: C β={c.get('c_s', {}).get('mean_beta')} "
                    f"(t_hac={c.get('c_s', {}).get('t_hac')})  "
                    f"F β={c.get('f_s', {}).get('mean_beta')} "
                    f"(t_hac={c.get('f_s', {}).get('t_hac')})  "
                    f"P β={c.get('p_s', {}).get('mean_beta')} "
                    f"(t_hac={c.get('p_s', {}).get('t_hac')})  增量R²={c.get('incremental_r2')}")

    report_root = get_report_root() / "backtest"
    report_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    fname = f"ic_analysis_{args.stock}_{stamp}" if args.stock else f"ic_analysis_{stamp}"
    path = report_root / f"{fname}.json"
    path.write_text(json.dumps({"generated_at": stamp,
                                "horizons": list(horizons),
                                "factors": ic_report,
                                "states": state_report,
                                "cfp_matrix": matrix_report,
                                "conditional_regression": cond_report},
                               ensure_ascii=False, indent=2, default=str),
                    encoding="utf-8")
    panel.to_csv(report_root / f"ic_panel_{stamp}.csv", index=False, encoding="utf-8-sig")
    logger.info(f"IC 报告已保存: {path}")
    logger.info("ic_analysis 完成 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
