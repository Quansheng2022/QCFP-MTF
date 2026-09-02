#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF P2 —— 月线行为引擎

流程：读月/周/季 K 线 → T1~T5 / VP_Regime / CBI / Cost Position / Stage
      → UPSERT 写入 qcfp_monthly_behavior

用法：
    python Core/QCFP_MTF/scripts/monthly_behavior_engine.py [--stock 00700]
        [--month-end 2026-07-31] [--dry-run]
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

import numpy as np
import pandas as pd

from QCFP_MTF.behavioral.cbi import build_cbi
from QCFP_MTF.behavioral.cost_position import build_cost_position
from QCFP_MTF.behavioral.monthly_stage import build_monthly_stage
from QCFP_MTF.behavioral.turnover_factors import build_turnover_factors
from QCFP_MTF.behavioral.volume_factors import build_volume_factors
from QCFP_MTF.behavioral.vp_matrix import build_vp_regime
from QCFP_MTF.common.db import connect
from QCFP_MTF.common.logger import setup_logger
from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.config.settings import get, load_qcfp_settings
from QCFP_MTF.data.loader import load_kline
from QCFP_MTF.data.quality import load_latest_quality_labels

GRADE_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF 月线行为引擎")
    parser.add_argument("--stock", help="只处理指定股票代码")
    parser.add_argument("--month-end", help="只处理指定月份（YYYY-MM-DD）")
    parser.add_argument("--dry-run", action="store_true", help="不写库，仅打印结果")
    args = parser.parse_args(argv)

    settings = load_qcfp_settings()
    from QCFP_MTF.decision.versions import MODEL_VERSION
    model_version = get(settings, "model.version", MODEL_VERSION)
    log_name = f"monthly_behavior_engine_{args.stock}" if args.stock else "monthly_behavior_engine"
    logger = setup_logger("monthly_behavior_engine", log_file=f"{log_name}.log", mode="w")
    logger.info("=== 月线行为引擎启动 ===")

    stocks = [args.stock] if args.stock else None
    m_df = load_kline("monthly", stocks=stocks)
    w_df = load_kline("weekly", stocks=stocks)
    q_df = load_kline("quarterly", stocks=stocks)
    if m_df.empty:
        logger.error("无可处理数据")
        return 1

    # 各因子模块
    turn = build_turnover_factors(m_df, settings)
    vol = build_volume_factors(m_df, settings)
    vp = build_vp_regime(m_df, vol, settings)
    cbi = build_cbi(m_df, settings)
    cost = build_cost_position(m_df, w_df, q_df, settings)

    # 合并
    base = m_df[["stock_code", "stock_name", "date", "change_percent", "turnover_rate"]].copy()
    base["month_end"] = pd.to_datetime(base["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    merged = base[["stock_code", "stock_name", "month_end", "change_percent", "turnover_rate"]]
    for df in (turn, vol, vp, cbi, cost):
        merged = merged.merge(
            df.drop(columns=[c for c in ("stock_name",) if c in df.columns]),
            on=["stock_code", "month_end"], how="left")

    merged = merged.sort_values(["stock_code", "month_end"]).reset_index(drop=True)
    if args.month_end:
        merged = merged[merged["month_end"] == args.month_end].reset_index(drop=True)
    if merged.empty:
        logger.error(f"指定月份 {args.month_end} 无数据")
        return 1

    # 阶段判定
    merged["monthly_behavior_state"] = build_monthly_stage(
        merged["m_vp_regime"], merged["turnover_liquidity_regime"])
    # VWAP 偏离 = 月末价 vs 月 VWAP
    merged["m_vwap_deviation"] = merged["cost_vs_monthly_vwap"]
    # 换手效率：每单位换手带来的收益
    merged["m_turnover_efficiency"] = (
        merged["change_percent"] / merged["turnover_rate"]
    ).where(merged["turnover_rate"].notna() & (merged["turnover_rate"] != 0))

    # 数据质量：三源最差
    labels = load_latest_quality_labels()
    label_map = {(r["stock_code"], r["data_type"]): r["grade"]
                 for _, r in labels.iterrows()}

    def _worst(stock):
        grades = [label_map.get((stock, "monthly_kline"), "D"),
                  label_map.get((stock, "weekly_kline"), "D"),
                  label_map.get((stock, "quarterly_kline"), "D")]
        return max(grades, key=lambda g: GRADE_ORDER.get(g, 3))

    merged["data_quality"] = merged["stock_code"].map(_worst)

    # 汇总日志
    latest = merged.sort_values("month_end").groupby("stock_code").tail(1)
    logger.info("=== 最新月份行为状态 ===")
    for _, r in latest.iterrows():
        logger.info(
            f"  {r['stock_code']} {r['month_end']}: {r['monthly_behavior_state']} "
            f"(T={r['turnover_liquidity_regime']}, VP={r['m_vp_regime']}, "
            f"CBI={r['cbi_score']:.1f} {r['cbi_state']}, cost={r['cost_position']}, dq={r['data_quality']})"
            if pd.notna(r["cbi_score"]) else
            f"  {r['stock_code']} {r['month_end']}: {r['monthly_behavior_state']} "
            f"(T={r['turnover_liquidity_regime']}, VP={r['m_vp_regime']}, CBI=NA, dq={r['data_quality']})"
        )

    # 报告
    report_root = get_report_root() / "monthly"
    report_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    fname = f"monthly_behavior_{args.stock}_{stamp}" if args.stock else f"monthly_behavior_{stamp}"
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
                r["stock_code"], r["stock_name"], r["month_end"],
                r["m_turnover_zscore"], r["m_turnover_pctl"], r["m_turnover_ma_ratio"],
                r["m_volume_ma_ratio"], r["m_volume_accel"], r["m_vwap_deviation"],
                r["m_turnover_efficiency"], r["m_vp_regime"],
                r["turnover_liquidity_regime"], r["monthly_behavior_state"],
                r["cbi_score"], r["cbi_state"], r["cost_position"],
                r["cost_vs_weekly_vwap"], r["cost_vs_monthly_vwap"],
                r["cost_vs_quarterly_vwap"],
                model_version, r["data_quality"], now,
            ))
        conn = connect()
        try:
            conn.executemany(
                """INSERT OR REPLACE INTO qcfp_monthly_behavior
                   (stock_code, stock_name, month_end,
                    m_turnover_zscore, m_turnover_pctl, m_turnover_ma_ratio,
                    m_volume_ma_ratio, m_volume_accel, m_vwap_deviation,
                    m_turnover_efficiency, m_vp_regime, turnover_liquidity_regime,
                    monthly_behavior_state, cbi_score, cbi_state, cost_position,
                    cost_vs_weekly_vwap, cost_vs_monthly_vwap, cost_vs_quarterly_vwap,
                    model_version, data_quality, update_time)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                rows,
            )
            conn.commit()
            logger.info(f"已 UPSERT {len(rows)} 行到 qcfp_monthly_behavior")
        finally:
            conn.close()
    else:
        logger.info("--dry-run 模式：未写库")

    logger.info("monthly_behavior_engine 完成 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
