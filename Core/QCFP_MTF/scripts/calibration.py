#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF P6 —— 参数校准（网格搜索）

候选参数：Chip Confidence 季度权重、REDUCE 目标仓位。
默认只输出 top-N 报告；--apply 写入 Config/qcfp_calibration.json。

用法：
    python Core/QCFP_MTF/scripts/calibration.py [--stock 00700]
        [--start 2021-01-01] [--apply]
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

from QCFP_MTF.backtest.calibration import run_grid, run_walk_forward_grid
from QCFP_MTF.common.db import connect
from QCFP_MTF.common.logger import setup_logger
from QCFP_MTF.common.paths import get_config_dir, get_report_root
from QCFP_MTF.config.settings import load_qcfp_settings
from QCFP_MTF.data.loader import load_derived, load_idx_hist, load_kline


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF 参数校准")
    parser.add_argument("--stock", help="只校准指定股票")
    parser.add_argument("--start", default="2021-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--apply", action="store_true", help="写入 qcfp_calibration.json")
    args = parser.parse_args(argv)

    settings = load_qcfp_settings()
    log_name = f"calibration_{args.stock}" if args.stock else "calibration"
    logger = setup_logger("calibration", log_file=f"{log_name}.log", mode="w")

    grid = []
    for q_w in (0.5, 0.6, 0.7):
        for reduce_pos in (0.3, 0.5, 0.7):
            grid.append({
                "fusion.chip_confidence.quarterly_chip_weight": q_w,
                "backtest.position_target.REDUCE": reduce_pos,
            })
    # 转成嵌套 dict 供 _deep_merge 使用
    nested_grid = []
    for combo in grid:
        merged = {}
        for key, val in combo.items():
            node = merged
            parts = key.split(".")
            for p in parts[:-1]:
                node = node.setdefault(p, {})
            node[parts[-1]] = val
        nested_grid.append(merged)

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

    stocks = [args.stock] if args.stock else None
    logger.info(f"开始网格校准：{len(nested_grid)} 组合 x "
                f"{args.stock or '全部股票'}，区间 {args.start} ~ 最新")
    result = run_grid(structural, monthly, weekly, chip, idx, weekly_kl,
                      settings, nested_grid, start=args.start,
                      stocks_filter=stocks, daily=daily)
    wf = run_walk_forward_grid(structural, monthly, weekly, chip, idx, weekly_kl,
                               settings, nested_grid, start=args.start,
                               end=args.end or str(pd.Timestamp.today().date()),
                               stocks_filter=stocks, daily=daily)

    report_root = get_report_root() / "backtest"
    report_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    fname = f"calibration_{args.stock}_{stamp}" if args.stock else f"calibration_{stamp}"
    path = report_root / f"{fname}.json"
    path.write_text(json.dumps({"generated_at": stamp,
                                "records": result.to_dict(orient="records"),
                                "walk_forward_oos": wf.to_dict(orient="records"),
                                "plateau": result.attrs.get("plateau")},
                               ensure_ascii=False, indent=2, default=str),
                    encoding="utf-8")
    logger.info(f"校准报告已保存: {path}")
    logger.info("=== top 组合（按 Sharpe）===")
    for _, r in result.head(args.top).iterrows():
        logger.info(f"  q_w={r.get('fusion', {}).get('chip_confidence', {}).get('quarterly_chip_weight')} "
                    f"reduce={r.get('backtest', {}).get('position_target', {}).get('REDUCE')} "
                    f"→ sharpe={r.get('sharpe')} 年化={r.get('annualized_return')} "
                        f"回撤={r.get('max_drawdown')}")
    plateau = result.attrs.get("plateau")
    if plateau:
        logger.info(f"参数平台：{plateau['n_plateau']}/{plateau['total']} 组合落在"
                    f"最优 Sharpe {plateau['best_sharpe']} ± {plateau['tol']} 内"
                    f"（平台越宽越稳健）")
    if not wf.empty:
        logger.info("=== Walk-forward OOS（训练窗选参 → 测试窗评估）===")
        for _, r in wf.iterrows():
            logger.info(f"  {r['window']} test {r['test_start']}~{r['test_end']}: "
                        f"年化={r.get('annualized_return')} Sharpe={r.get('sharpe')} "
                        f"（train_sharpe={r.get('train_sharpe')}，最佳参数={r.get('best_params')}）")
        stability = wf.attrs.get("param_stability")
        if stability:
            logger.info(f"参数稳定性：{stability['stable_windows']}/{stability['n_windows']} "
                        f"个窗口选择同一最优参数（{stability['mode_params']}）")

    if args.apply and not result.empty:
        best = result.iloc[0]
        out = {"model_version": settings.get("model", {}).get("version"),
               "calibrated_at": stamp,
               "best": {"fusion.chip_confidence.quarterly_chip_weight":
                        best.get("fusion", {}).get("chip_confidence", {}).get("quarterly_chip_weight"),
                        "backtest.position_target.REDUCE":
                        best.get("backtest", {}).get("position_target", {}).get("REDUCE")},
               "sharpe": best.get("sharpe")}
        (get_config_dir() / "qcfp_calibration.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("已写入 Config/qcfp_calibration.json（主配置未改动）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
