#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF —— 四池股票池报告（散户执行层，V24）

A 池（Institutional Trend）：机构权限 ALLOW/STRONG_ALLOW + 周线突破/盘整 + Risk≤Medium
B 池（Recovery）：机构状态 RECOVERY + 52W 极低位 + 周线突破（值得盯，非立即买）
C 池（Swing Watch）：机构权限 WATCH + 日线 Setup（突破/回踩/吸筹）
D 池（Risk）：派发/破位/投降（应回避）

用法：python Core/QCFP_MTF/scripts/stock_pool_report.py [--stock 00371]
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

from QCFP_MTF.common.db import connect
from QCFP_MTF.common.logger import setup_logger
from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.config.settings import load_qcfp_settings
from QCFP_MTF.decision.institutional_filter import (institutional_pressure,
                                                    institutional_state)
from QCFP_MTF.decision.institutional_permission import evaluate_institutional_permission
from QCFP_MTF.decision.retail import classify_pool, retail_action, traffic_light


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF A/B 股票池")
    parser.add_argument("--stock", default=None)
    args = parser.parse_args(argv)
    settings = load_qcfp_settings()
    logger = setup_logger("stock_pool_report", log_file="stock_pool_report.log", mode="a")
    logger.info("=== A/B 股票池报告启动 ===")

    conn = connect()
    try:
        d = pd.read_sql_query(
            """SELECT d.stock_code, d.stock_name, d.decision_date, d.mtf_regime,
                      d.structural_regime, d.monthly_behavior_state, d.tactical_signal,
                      d.risk_level, d.des_score, d.des_band,
                      d.chip_stability_confidence, d.market_context,
                      d.structure_behavior_alignment, d.data_quality,
                      dt.daily_state
               FROM qcfp_mtf_decision d
               LEFT JOIN qcfp_daily_tactical dt
                 ON dt.stock_code = d.stock_code
                AND dt.trade_date = (
                    SELECT MAX(dt2.trade_date) FROM qcfp_daily_tactical dt2
                    WHERE dt2.stock_code = d.stock_code
                      AND dt2.trade_date <= d.decision_date)
               WHERE d.decision_date = (
                   SELECT MAX(d2.decision_date) FROM qcfp_mtf_decision d2
                   WHERE d2.stock_code = d.stock_code)""", conn)
        s = pd.read_sql_query(
            """SELECT q.stock_code, q.structural_regime, q.q_position_52w,
                      q.f_state, q.c_state, q.p_state
               FROM qcfp_quarterly_structural q
               WHERE q.period_end = (
                   SELECT MAX(q2.period_end) FROM qcfp_quarterly_structural q2
                   WHERE q2.stock_code = q.stock_code)""", conn)
    finally:
        conn.close()
    if args.stock:
        d = d[d["stock_code"] == args.stock]
    d = d.merge(s, on="stock_code", how="left", suffixes=("", "_q"))
    d["inst_state"] = d.apply(
        lambda r: institutional_state(r.get("c_state"), r.get("f_state"),
                                      r.get("p_state")), axis=1)
    d["inst_pressure"] = d.apply(
        lambda r: institutional_pressure(r.get("c_state"), r.get("f_state")), axis=1)
    d["inst_perm"] = d.apply(
        lambda r: evaluate_institutional_permission(
            institutional_state_name=r["inst_state"], pressure=r["inst_pressure"],
            persistence=1 if r.get("f_state") == "F↑" else 0,
            divergence=r.get("structure_behavior_alignment") == "Divergence",
            confidence=r.get("chip_stability_confidence") or "Medium",
            data_quality=r.get("data_quality") or "B", settings=settings), axis=1)
    d["inst_permission"] = d["inst_perm"].map(lambda x: x.permission)
    d["pool"] = d.apply(lambda r: classify_pool(r, settings), axis=1)
    d["pool4"] = d.apply(_pool4, axis=1)
    d["traffic_light"] = d.apply(traffic_light, axis=1)
    d["retail_action"] = d.apply(retail_action, axis=1)
    pools = {p: d[d["pool4"] == p].sort_values("decision_date", ascending=False)
             for p in ("A", "B", "C", "D")}
    logger.info(
        f"A 池(趋势) {len(pools['A'])} | B 池(恢复) {len(pools['B'])} | "
        f"C 池(观察) {len(pools['C'])} | D 池(风险) {len(pools['D'])}")
    perm_dist = d["inst_permission"].value_counts().to_dict()
    logger.info(f"权限分布：{perm_dist}")
    for name, pool in (("A", pools["A"]), ("B", pools["B"]),
                       ("C", pools["C"]), ("D", pools["D"])):
        for _, r in pool.iterrows():
            pos = r.get("q_position_52w")
            logger.info(
                f"  {name}池 {r['stock_code']} {r.get('stock_name') or ''} "
                f"{r['decision_date']}: {r['inst_state']}/{r['inst_permission']} "
                f"{r['retail_action']} risk={r['risk_level']} DES={r['des_score']} "
                f"52w={pos if pd.isna(pos) else round(pos, 3)}")

    report_root = get_report_root() / "stock_pool"
    report_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    lines = [f"# QCFP-MTF 四池股票池（{stamp}）\n",
             f"- A 池(趋势) {len(pools['A'])} ｜ B 池(恢复观察) {len(pools['B'])} ｜ "
             f"C 池(观察) {len(pools['C'])} ｜ D 池(风险) {len(pools['D'])}\n"]
    lines.append(f"- 机构权限分布：{perm_dist}\n")
    labels = {"A": "A 池（Institutional Trend）", "B": "B 池（Recovery）",
              "C": "C 池（Swing Watch）", "D": "D 池（Risk）"}
    for key, pool in pools.items():
        name = labels[key]
        lines.append(f"## {name}\n")
        if pool.empty:
            lines.append("（空）\n")
            continue
        lines.append("| 代码 | 名称 | 决策日 | 机构状态 | 权限 | 交易状态 | 风险 | DES | 日线 | 52W |")
        lines.append("| :-- | :-- | :-- | :-- | :-- | :-- | :-- | --: | :-- | --: |")
        for _, r in pool.iterrows():
            pos = r.get("q_position_52w")
            lines.append(
                f"| {r['stock_code']} | {r.get('stock_name') or '—'} | "
                f"{r['decision_date']} | {r['inst_state']} | {r['inst_permission']} | "
                f"{r['retail_action']} | {r['risk_level']} | {r['des_score']} | "
                f"{r.get('daily_state') or '—'} | "
                f"{round(pos, 4) if pd.notna(pos) else '—'} |")
        lines.append("")
    (report_root / f"stock_pool_{stamp}.md").write_text(
        "\n".join(lines), encoding="utf-8")
    d.to_csv(report_root / f"stock_pool_{stamp}.csv", index=False, encoding="utf-8-sig")
    (report_root / f"stock_pool_{stamp}.json").write_text(
        json.dumps({"generated_at": stamp,
                    "pools": {k: v.to_dict(orient="records")
                              for k, v in pools.items()}},
                   ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    logger.info(f"股票池报告已保存: Report/QCFP_MTF/stock_pool/stock_pool_{stamp}.{{md,csv,json}}")
    logger.info("stock_pool_report 完成 ✅")
    return 0


def _pool4(r) -> str:
    """四池分类"""
    perm = r.get("inst_permission")
    risk = r.get("risk_level")
    des = r.get("des_score") or 0
    daily = r.get("daily_state")
    weekly = r.get("tactical_signal")
    if r.get("inst_state") in ("DISTRIBUTION", "DISTRIBUTION_STRONG",
                               "CAPITULATION") or des >= 5 or weekly == "Breakdown":
        return "D"
    if perm in ("ALLOW", "STRONG_ALLOW") and weekly in ("Breakout", "Consolidation") \
            and risk in ("Low", "Medium"):
        return "A"
    if r.get("inst_state") == "RECOVERY" and weekly == "Breakout":
        return "B"
    if perm == "WATCH" and daily in ("DAILY_BREAKOUT", "DAILY_PULLBACK",
                                     "DAILY_ACCUMULATION") \
            and risk in ("Low", "Medium") and des < 5:
        return "C"
    return "D" if risk == "Extreme" else None


if __name__ == "__main__":
    sys.exit(main())
