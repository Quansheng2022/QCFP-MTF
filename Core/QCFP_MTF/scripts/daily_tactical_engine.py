#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF L4 —— 日线战术引擎（Tactical Timing Layer）

定位：Q/M/W 决定战略方向，Daily 只负责"什么时候做"：
    DAILY_ACCUMULATION / DAILY_BREAKOUT / DAILY_PULLBACK /
    DAILY_DISTRIBUTION / DAILY_NEUTRAL
因子：F（日资金流机构净流入代理 + PIT Z）+ P（均线/趋势/量比/20 日 VWAP/突破），C 不使用。
输出：UPSERT 写入 qcfp_daily_tactical（每股票 × 每日）。

用法：
    python Core/QCFP_MTF/scripts/daily_tactical_engine.py [--stock 00700]
        [--date 2026-08-14] [--dry-run]
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
from QCFP_MTF.config.settings import get, load_qcfp_settings
from QCFP_MTF.data.loader import load_kline, load_moneyflow
from QCFP_MTF.data.quality import load_latest_quality_labels
from QCFP_MTF.tactical.daily_tactical import (build_daily_states,
                                              build_flow_factors,
                                              build_price_factors)

GRADE_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF 日线战术引擎")
    parser.add_argument("--stock", help="只处理指定股票代码")
    parser.add_argument("--date", help="只处理指定交易日（YYYY-MM-DD）")
    parser.add_argument("--dry-run", action="store_true", help="不写库，仅打印结果")
    args = parser.parse_args(argv)

    settings = load_qcfp_settings()
    from QCFP_MTF.decision.versions import MODEL_VERSION
    model_version = get(settings, "model.version", MODEL_VERSION)
    log_name = f"daily_tactical_engine_{args.stock}" if args.stock else "daily_tactical_engine"
    logger = setup_logger("daily_tactical_engine", log_file=f"{log_name}.log", mode="w")
    logger.info("=== 日线战术引擎启动 ===")

    stocks = [args.stock] if args.stock else None
    d_df = load_kline("daily", stocks=stocks)
    mf_df = load_moneyflow("daily", stocks=stocks)
    if d_df.empty:
        logger.error("无可处理数据")
        return 1

    p_f = build_price_factors(d_df, settings)
    f_f = build_flow_factors(mf_df, settings)
    merged = build_daily_states(p_f, f_f, settings)
    name_map = d_df[["stock_code", "stock_name"]].drop_duplicates("stock_code")
    merged = merged.merge(name_map, on="stock_code", how="left")
    merged = merged.sort_values(["stock_code", "trade_date"]).reset_index(drop=True)

    if args.date:
        merged = merged[merged["trade_date"] == args.date].reset_index(drop=True)
    if merged.empty:
        logger.error(f"指定日期 {args.date} 无数据")
        return 1

    labels = load_latest_quality_labels()
    label_map = {(r["stock_code"], r["data_type"]): r["grade"]
                 for _, r in labels.iterrows()}

    def _dq(code):
        g1 = label_map.get((code, "daily_kline"), "D")
        g2 = label_map.get((code, "daily_moneyflow"), "D")
        return max(g1, g2, key=lambda g: GRADE_ORDER.get(g, 3))

    merged["data_quality"] = merged["stock_code"].map(_dq)

    latest = merged.sort_values("trade_date").groupby("stock_code").tail(1)
    logger.info("=== 最新日线战术状态 ===")
    for _, r in latest.iterrows():
        logger.info(
            f"  {r['stock_code']} {r['trade_date']}: {r['daily_state']} "
            f"(trend={r['d_trend_score']:.1f}, vol={r['d_vol_ratio']:.2f}, "
            f"flow_z={r['d_flow_z'] if pd.isna(r['d_flow_z']) else round(r['d_flow_z'], 2)}, "
            f"dq={r['data_quality']})")

    report_root = get_report_root() / "daily_tactical"
    report_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    fname = f"daily_tactical_{args.stock}_{stamp}" if args.stock else f"daily_tactical_{stamp}"
    csv_path = report_root / f"{fname}.csv"
    json_path = report_root / f"{fname}.json"
    merged.to_csv(csv_path, index=False, encoding="utf-8-sig")
    json_path.write_text(
        json.dumps({"generated_at": stamp, "model_version": model_version,
                    "records": merged.to_dict(orient="records")},
                   ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    logger.info(f"报告已保存: {csv_path}")

    if not args.dry_run:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = []
        for _, r in merged.iterrows():
            rows.append((
                r["stock_code"], r.get("stock_name"), r["trade_date"],
                r["daily_state"],
                int(r["d_breakout"] or 0), int(r["d_distribution"] or 0),
                int(r["d_pullback"] or 0), int(r["d_accumulation"] or 0),
                int(r["d_decline"] or 0),
                r["d_trend_score"], r["d_vol_ratio"], r["d_near_high"],
                r.get("d_inst_flow"), r.get("d_flow_z"), r.get("d_flow_slope"),
                model_version, r["data_quality"], now,
            ))
        conn = connect()
        try:
            conn.executemany(
                """INSERT OR REPLACE INTO qcfp_daily_tactical
                   (stock_code, stock_name, trade_date, daily_state,
                    d_breakout, d_distribution, d_pullback, d_accumulation, d_decline,
                    d_trend_score, d_vol_ratio, d_near_high,
                    d_inst_flow, d_flow_z, d_flow_slope,
                    model_version, data_quality, update_time)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                rows,
            )
            conn.commit()
            logger.info(f"已 UPSERT {len(rows)} 行到 qcfp_daily_tactical")
        finally:
            conn.close()
    else:
        logger.info("--dry-run 模式：未写库")

    logger.info("daily_tactical_engine 完成 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
