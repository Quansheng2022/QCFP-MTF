#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF P3 —— 周线战术引擎

流程：读周 K 线 → 放量/缩量、换手偏离/极端、VWAP 偏离、均线斜率
      → 突破/破位 → 4 种战术信号 → UPSERT 写入 qcfp_weekly_tactical

用法：
    python Core/QCFP_MTF/scripts/weekly_tactical_engine.py [--stock 00700]
        [--week-end 2026-08-14] [--dry-run]
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
from QCFP_MTF.data.loader import load_kline
from QCFP_MTF.data.quality import load_latest_quality_labels
from QCFP_MTF.tactical.weekly_signal import build_signal
from QCFP_MTF.tactical.weekly_turnover import build_turnover_factors
from QCFP_MTF.tactical.weekly_volume import build_volume_factors
from QCFP_MTF.tactical.weekly_vwap import build_vwap_factors

GRADE_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF 周线战术引擎")
    parser.add_argument("--stock", help="只处理指定股票代码")
    parser.add_argument("--week-end", help="只处理指定周（YYYY-MM-DD）")
    parser.add_argument("--dry-run", action="store_true", help="不写库，仅打印结果")
    args = parser.parse_args(argv)

    settings = load_qcfp_settings()
    from QCFP_MTF.decision.versions import MODEL_VERSION
    model_version = get(settings, "model.version", MODEL_VERSION)
    log_name = f"weekly_tactical_engine_{args.stock}" if args.stock else "weekly_tactical_engine"
    logger = setup_logger("weekly_tactical_engine", log_file=f"{log_name}.log", mode="w")
    logger.info("=== 周线战术引擎启动 ===")

    w_df = load_kline("weekly", stocks=[args.stock] if args.stock else None)
    if w_df.empty:
        logger.error("无可处理数据")
        return 1

    vol = build_volume_factors(w_df, settings)
    turn = build_turnover_factors(w_df, settings)
    vwap = build_vwap_factors(w_df, settings)
    sig = build_signal(w_df, vol, vwap, settings)

    base = w_df[["stock_code", "stock_name", "date"]].copy()
    base["week_end"] = pd.to_datetime(base["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    merged = base[["stock_code", "stock_name", "week_end"]]
    for df in (vol, turn, vwap, sig):
        merged = merged.merge(
            df.drop(columns=[c for c in ("stock_name",) if c in df.columns]),
            on=["stock_code", "week_end"], how="left")
    merged = merged.sort_values(["stock_code", "week_end"]).reset_index(drop=True)
    if args.week_end:
        merged = merged[merged["week_end"] == args.week_end].reset_index(drop=True)
    if merged.empty:
        logger.error(f"指定周 {args.week_end} 无数据")
        return 1

    # 数据质量：weekly_kline 审计等级
    labels = load_latest_quality_labels()
    label_map = {(r["stock_code"], r["data_type"]): r["grade"]
                 for _, r in labels.iterrows()}
    merged["data_quality"] = merged["stock_code"].map(
        lambda s: label_map.get((s, "weekly_kline"), "D"))

    latest = merged.sort_values("week_end").groupby("stock_code").tail(1)
    logger.info("=== 最新周战术信号 ===")
    for _, r in latest.iterrows():
        logger.info(
            f"  {r['stock_code']} {r['week_end']}: {r['tactical_signal']} "
            f"(vol_breakout={r['w_volume_breakout']}, vol_shrink={r['w_volume_shrink']}, "
            f"turn_spike={r['w_turnover_spike']}, vwap={r['w_vwap_deviation']:.2%}, "
            f"slope={r['w_ma_slope']}, dq={r['data_quality']})"
            if pd.notna(r["w_vwap_deviation"]) else
            f"  {r['stock_code']} {r['week_end']}: {r['tactical_signal']} (dq={r['data_quality']})"
        )

    report_root = get_report_root() / "weekly"
    report_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    fname = f"weekly_tactical_{args.stock}_{stamp}" if args.stock else f"weekly_tactical_{stamp}"
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
                r["stock_code"], r["stock_name"], r["week_end"],
                r["w_turnover_deviation"], int(r["w_turnover_spike"] or 0),
                int(r["w_volume_breakout"] or 0), int(r["w_volume_shrink"] or 0),
                r["w_vwap_deviation"], r["w_ma_slope"],
                int(r["w_breakout"] or 0), int(r["w_breakdown"] or 0),
                r["tactical_signal"], model_version, r["data_quality"], now,
            ))
        conn = connect()
        try:
            conn.executemany(
                """INSERT OR REPLACE INTO qcfp_weekly_tactical
                   (stock_code, stock_name, week_end,
                    w_turnover_deviation, w_turnover_spike, w_volume_breakout,
                    w_volume_shrink, w_vwap_deviation, w_ma_slope,
                    w_breakout, w_breakdown, tactical_signal,
                    model_version, data_quality, update_time)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                rows,
            )
            conn.commit()
            logger.info(f"已 UPSERT {len(rows)} 行到 qcfp_weekly_tactical")
        finally:
            conn.close()
    else:
        logger.info("--dry-run 模式：未写库")

    logger.info("weekly_tactical_engine 完成 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
