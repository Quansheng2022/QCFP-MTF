#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF —— Market Regime Gate 实验（P2）

Model A：原始 QCFP
Model B：QCFP + risk_off 降杠杆（market_context=risk_off 时 target × risk_off_factor）

对比 Return / Sharpe / Sortino / MDD / PF / 换手 / risk_off 分层亏损。
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
from QCFP_MTF.backtest.performance import by_year, evaluate
from QCFP_MTF.common.db import connect
from QCFP_MTF.common.logger import setup_logger
from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.config.settings import load_qcfp_settings
from QCFP_MTF.data.loader import load_derived, load_idx_hist, load_kline


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF 市场环境门实验")
    parser.add_argument("--factor", type=float, default=0.25,
                        help="risk_off 时 target 的缩放系数（默认 0.25）")
    parser.add_argument("--start", default="2021-01-01")
    parser.add_argument("--end", default=None)
    args = parser.parse_args(argv)

    settings = load_qcfp_settings()
    logger = setup_logger("regime_gate_test", log_file="regime_gate_test.log", mode="a")
    logger.info("=== Market Regime Gate 实验启动 ===")

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
    end = args.end or weekly["week_end"].max()

    sig_a = build_signal_timeline(structural, monthly, weekly, chip, idx, settings)
    sig_b = sig_a.copy()
    sig_b.loc[sig_b["market_context"] == "risk_off", "target"] *= args.factor

    bt_a = run_backtest(sig_a, weekly_kl, settings, start=args.start, end=end)
    bt_b = run_backtest(sig_b, weekly_kl, settings, start=args.start, end=end)

    def _report(bt, label):
        port = portfolio_returns(bt)
        perf = evaluate(port["portfolio_return"], turnover=port["avg_turnover"])
        regime = by_market_regime_like(port, bt)
        return {"model": label, **perf, "regime": regime}

    def by_market_regime_like(port, bt):
        pr = port.set_index("week_end")["portfolio_return"]
        reg = bt.groupby("week_end")["market_regime"].first().reindex(pr.index).fillna("neutral")
        out = {}
        for name, g in pr.groupby(reg):
            out[name] = {
                "annualized_return": float((1 + g).prod() ** (52 / max(len(g), 1)) - 1),
                "sharpe": float(g.mean() / g.std(ddof=0) * 52 ** 0.5)
                if g.std(ddof=0) > 0 else None,
            }
        return out

    ra, rb = _report(bt_a, "A_raw"), _report(bt_b, "B_risk_off_gate")
    for r in (ra, rb):
        ro = r["regime"].get("risk_off", {})
        logger.info(
            f"{r['model']}: 年化 {r['annualized_return']:.2%}  Sharpe {r['sharpe']}  "
            f"Sortino {r['sortino']}  回撤 {r['max_drawdown']:.2%}  "
            f"PF {r['profit_factor']}  换手 {r['annual_turnover']:.2f}  | "
            f"risk_off 年化 {ro.get('annualized_return'):.2%} Sharpe {ro.get('sharpe')}")

    result = pd.DataFrame([{k: v for k, v in r.items() if k != "regime"}
                           for r in (ra, rb)])
    result["risk_off_annualized"] = [ra["regime"].get("risk_off", {}).get("annualized_return"),
                                     rb["regime"].get("risk_off", {}).get("annualized_return")]
    result["risk_off_sharpe"] = [ra["regime"].get("risk_off", {}).get("sharpe"),
                                 rb["regime"].get("risk_off", {}).get("sharpe")]

    report_root = get_report_root() / "backtest"
    report_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    (report_root / f"regime_gate_{stamp}.json").write_text(
        json.dumps({"generated_at": stamp, "factor": args.factor,
                    "models": [ra, rb]}, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")
    result.to_csv(report_root / f"regime_gate_{stamp}.csv", index=False, encoding="utf-8-sig")
    logger.info(f"报告已保存: Report/QCFP_MTF/backtest/regime_gate_{stamp}.{{json,csv}}")
    logger.info("regime_gate_test 完成 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
