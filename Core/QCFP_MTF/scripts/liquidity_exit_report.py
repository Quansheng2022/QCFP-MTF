#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF 2.8 —— Liquidity-aware Exit Report（流动性感知退出报告）

回答"如果现在必须退出，这笔仓位几天能出完、成本多高"：
    ADV（近 20 日均成交额）→ Exit Days → Impact → Slippage + Stress Cost
    → LIQUIDITY_OK/FAIR/LOW →（EXIT_REQUIRED + LOW）→ DELEVERAGE_PLAN

用法：
    python Core/QCFP_MTF/scripts/liquidity_exit_report.py --stock 01951
        [--position-value 1000000] [--exit-required]
        [--date 2026-08-24]
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

from QCFP_MTF.common.db import connect
from QCFP_MTF.common.logger import setup_logger
from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.execution.liquidity_exit import evaluate_liquidity_exit


def _adv(conn, stock, date, window=20):
    """近 window 个交易日日均成交额（amount 字段）。"""
    r = conn.execute(
        """SELECT AVG(amount) AS adv, COUNT(*) AS n
           FROM (SELECT amount FROM hk_hist_daily_kline
                 WHERE stock_code=? AND date<=?
                 ORDER BY date DESC LIMIT ?)""",
        (stock, date, window)).fetchone()
    return float(r["adv"]) if r and r["adv"] else 0.0


def _latest_close(conn, stock, date):
    r = conn.execute(
        "SELECT close FROM hk_hist_daily_kline WHERE stock_code=? AND date<=? "
        "ORDER BY date DESC LIMIT 1", (stock, date)).fetchone()
    return float(r["close"]) if r else 0.0


def _position_value(conn, stock, date):
    """优先用 Ledger final_target × 最新收盘价。"""
    row = conn.execute(
        "SELECT final_target FROM qcfp_decision_ledger "
        "WHERE stock_code=? AND decision_date<=? AND status='ACTIVE' "
        "ORDER BY decision_date DESC LIMIT 1", (stock, date)).fetchone()
    if row and row["final_target"]:
        close = _latest_close(conn, stock, date)
        return float(row["final_target"]) * close
    return 0.0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF 流动性感知退出报告")
    parser.add_argument("--stock", required=True)
    parser.add_argument("--date", default=None)
    parser.add_argument("--position-value", type=float, default=None,
                        help="持仓市值（缺省用 Ledger final_target × 收盘价）")
    parser.add_argument("--adv", type=float, default=None,
                        help="日均成交额（缺省用 DB 近 20 日均值）")
    parser.add_argument("--exit-required", action="store_true",
                        help="是否处于强制退出状态（Hard Exit/治理）")
    parser.add_argument("--participation", type=float, default=0.10)
    args = parser.parse_args(argv)
    logger = setup_logger("liquidity_exit_report",
                          log_file="liquidity_exit_report.log", mode="a")

    from QCFP_MTF.scripts.dss_report import _latest_decision
    conn = connect()
    try:
        date = args.date or _latest_decision(conn, args.stock)
        adv = args.adv if args.adv else _adv(conn, args.stock, date)
        pv = args.position_value if args.position_value is not None \
            else _position_value(conn, args.stock, date)
    finally:
        conn.close()

    result = evaluate_liquidity_exit(
        position_value=pv, adv=adv, participation=args.participation,
        exit_required=args.exit_required, start_date=date)
    output = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stock": args.stock, "decision_date": date,
        "position_value": result.position_value,
        "adv": result.adv,
        "participation": result.participation,
        "exit_days": result.exit_days,
        "impact": result.impact,
        "slippage_bps": result.slippage_bps,
        "stress_cost_bps": result.stress_cost_bps,
        "liquidity_flag": result.liquidity_flag,
        "exit_required": result.exit_required,
        "deleverage_plan": result.deleverage_plan,
        "reasons": list(result.reasons),
    }
    report_root = get_report_root() / "liquidity_exit"
    report_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    json_path = report_root / f"liquidity_exit_{args.stock}_{stamp}.json"
    json_path.write_text(json.dumps(output, ensure_ascii=False, indent=2,
                                    default=str), encoding="utf-8")
    md = _to_md(output)
    md_path = report_root / f"liquidity_exit_{args.stock}_{stamp}.md"
    md_path.write_text(md, encoding="utf-8")
    print(md)
    logger.info(f"{args.stock} {date} flag={result.liquidity_flag} "
                f"days={result.exit_days} pv={result.position_value}")
    return 0


def _to_md(o: dict) -> str:
    flag = o["liquidity_flag"]
    lines = [
        f"# Liquidity-aware Exit Report　{o['stock']}　{o['decision_date']}",
        "",
        f"**流动性标记：{flag}**",
        "",
        f"- 持仓市值：{o['position_value']:,.0f}",
        f"- ADV（日均成交额）：{o['adv']:,.0f}",
        f"- 参与率上限：{o['participation']:.0%}",
        f"- 预计退出天数：{o['exit_days']}",
        f"- 市场冲击：{o['impact']:.4%}",
        f"- 滑点 + 压力成本：{o['slippage_bps']:.0f} + "
        f"{o['stress_cost_bps']:.0f} bps",
        "",
    ]
    if o["exit_required"] and flag == "LIQUIDITY_LOW":
        plan = o["deleverage_plan"]
        lines += ["## DELEVERAGE_PLAN（分批退出计划）", ""]
        if plan.get("slices"):
            lines += ["| 日期 | 退出金额 | 累计占比 |", "| --- | --- | --- |"]
            for s in plan["slices"]:
                lines.append(
                    f"| {s['date']} | {s['amount']:,.0f} | "
                    f"{s['cumulative_pct']:.1%} |")
            lines += ["", f"- 预计 {plan['days']} 天完成退出"]
        else:
            lines += [f"- {plan.get('note', '无计划')}", ""]
    elif o["reasons"]:
        lines += ["## 提示", ""]
        lines += [f"- {r}" for r in o["reasons"]]
        lines += [""]
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
