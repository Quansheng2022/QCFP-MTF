#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF 2.5 —— Execution Ablation（执行层消融）

验证执行假设对结果的影响：
    ① 成本多倍压力（base / 1.5× / 2× / 3×）
    ② T+1 生效无偏（position=target.shift(1)，杜绝同周执行）

用法：
    python Core/QCFP_MTF/scripts/execution_ablation.py
        [--stock 01951] [--engine legacy|canonical]
        [--multipliers 1.0,1.5,2.0,3.0]
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

from QCFP_MTF.backtest.engine import portfolio_returns, run_backtest
from QCFP_MTF.backtest.performance import evaluate as evaluate_perf
from QCFP_MTF.common.db import connect
from QCFP_MTF.common.logger import setup_logger
from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.config.settings import load_qcfp_settings
from QCFP_MTF.data.loader import load_derived, load_idx_hist, load_kline


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF Execution Ablation")
    parser.add_argument("--stock", default=None)
    parser.add_argument("--start", default="2021-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument("--multipliers", default="1.0,1.5,2.0,3.0")
    parser.add_argument("--scenarios", default="",
                        help="逗号分隔执行情景（base,stress,extreme）")
    args = parser.parse_args(argv)
    settings = load_qcfp_settings()
    logger = setup_logger("execution_ablation",
                          log_file="execution_ablation.log", mode="a")
    logger.info("=== Execution Ablation 启动 ===")

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
    # MTR Closure（Sprint A）：正式 Ablation 只允许 Canonical-only；
    # 旧策略研究请使用 run_legacy_shadow_comparator（SHADOW_ONLY）。
    from QCFP_MTF.backtest.canonical_runs import run_canonical_ablation
    signals = run_canonical_ablation(
        structural, monthly, weekly, chip, idx, settings,
        ablations=[{"label": "BASE", "settings": settings}],
        stocks=stocks, weekly_kl=weekly_kl, daily=daily,
        run_id="exec_abl")["variants"]["BASE"]["signals"]
    if signals.empty:
        logger.error("无可回测信号")
        return 1

    rows = []
    from QCFP_MTF.execution.simulator import SCENARIO_ALIASES
    scenarios = []
    for x in args.scenarios.split(","):
        x = x.strip().lower()
        if not x:
            continue
        scenarios.append(SCENARIO_ALIASES.get(x, x.upper()))
    for sc in scenarios or ["BASE"]:
        from QCFP_MTF.execution.simulator import SCENARIOS, apply_scenario
        s2 = apply_scenario(settings, sc)
        sc_cfg = SCENARIOS[sc]
        bt = run_backtest(signals, weekly_kl, s2,
                          start=args.start, end=args.end)
        port = portfolio_returns(bt)
        perf = evaluate_perf(port["portfolio_return"],
                             turnover=port["avg_turnover"])
        rows.append({
            "scenario": sc,
            "fill_rate": sc_cfg["fill_rate"],
            "participation_rate": sc_cfg["participation_rate"],
            "annualized_return": perf.get("annualized_return"),
            "sharpe": perf.get("sharpe"),
            "max_drawdown": perf.get("max_drawdown"),
            "profit_factor": perf.get("profit_factor"),
            "annual_turnover": perf.get("annual_turnover"),
            "annual_cost": round(float(bt["cost"].mean() * 52), 6),
        })
        logger.info(
            f"{sc}: 年化 {perf['annualized_return']:.2%}  "
            f"Sharpe {perf['sharpe']}  MDD {perf['max_drawdown']:.2%}  "
            f"PF {perf['profit_factor']}  换手 {perf['annual_turnover']:.2f}  "
            f"fill={sc_cfg['fill_rate']:.0%}")

    # T+1 无偏验证：仓位 = target.shift(1)，首周无暴露
    t1_ok = bool(bt.iloc[0]["position"] == 0.0)
    result = pd.DataFrame(rows)
    # 净 Alpha 存活：各情景净收益 / 低成本(C0)净收益
    c0_rows = result[result["scenario"] == "C0_LOW"]
    c0_ret = float(c0_rows["annualized_return"].iloc[0]) \
        if len(c0_rows) else None
    result["alpha_survival"] = [
        round(float(r["annualized_return"]) / c0_ret, 4)
        if c0_ret is not None and c0_ret != 0 else None
        for _, r in result.iterrows()]
    # 盈亏平衡：PF 首次跌破 1 的档位
    breakeven = None
    for _, r in result.iterrows():
        if r["profit_factor"] is not None and r["profit_factor"] < 1.0:
            breakeven = r["scenario"]
            break
    out_dir = get_report_root() / "backtest"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    focus = args.stock or "all"
    base = f"execution_ablation_{focus}_{stamp}"
    result.to_csv(out_dir / f"{base}.csv", index=False,
                  encoding="utf-8-sig")
    (out_dir / f"{base}.json").write_text(
        json.dumps({"generated_at": stamp, "engine": args.engine,
                    "t_plus_1_verified": t1_ok, "breakeven_cost_x": breakeven,
                    "rows": result.to_dict(orient="records")},
                   ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")
    md = ["# QCFP-MTF Execution Ablation\n",
          f"- 引擎：{args.engine}　焦点：{args.stock or '全部'}\n",
          f"- T+1 生效无偏验证：{'✅ position=target.shift(1)' if t1_ok else '❌'}\n",
          f"- 盈亏平衡档位：{breakeven if breakeven else '三情景内未跌破 PF=1'}\n",
          "## 执行情景压力（BASE / STRESS / EXTREME）\n",
          "| 情景 | 成交率 | 参与率 | 年化 | Sharpe | MDD | PF | 换手 |",
          "| :-- | --: | --: | --: | --: | --: | --: | --: |"]
    for _, r in result.iterrows():
        md.append(
            f"| {r['scenario']} | {r['fill_rate']:.0%} | "
            f"{r['participation_rate']:.0%} | {r['annualized_return']:.2%} | "
            f"{r['sharpe']} | {r['max_drawdown']:.2%} | "
            f"{r['profit_factor']} | {r['annual_turnover']:.2f} |")
    (out_dir / f"{base}.md").write_text("\n".join(md), encoding="utf-8")
    logger.info(f"报告已保存: Report/QCFP_MTF/backtest/{base}.{{md,csv,json}}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
