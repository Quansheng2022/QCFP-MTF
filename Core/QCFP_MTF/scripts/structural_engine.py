#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF P1 —— 季度结构引擎

流程：读源表 → C/F/P 因子 → FSM-1（直接映射 + 降级/保持）→ Core Score
      → 三维背离（CPD/FPD/CFD）→ UPSERT 写入 qcfp_quarterly_structural

用法：
    python Core/QCFP_MTF/scripts/structural_engine.py [--stock 00700]
        [--period-end 2026-06-30] [--dry-run]
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

import numpy as np
import pandas as pd

from QCFP_MTF.common.db import connect
from QCFP_MTF.common.asof import (apply_disclosure_overrides,
                                  load_disclosure_overrides)
from QCFP_MTF.common.logger import setup_logger
from QCFP_MTF.common.normalization import rolling_zscore
from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.config.settings import get, load_qcfp_settings
from QCFP_MTF.data.loader import load_derived, load_kline
from QCFP_MTF.data.quality import load_latest_quality_labels
from QCFP_MTF.structural.chip_factors import build_c_factors
from QCFP_MTF.structural.divergence import compute_divergence
from QCFP_MTF.structural.flow_factors import build_f_factors
from QCFP_MTF.structural.price_factors import build_p_factors
from QCFP_MTF.structural.structural_regime import (map_core_score,
                                                   resolve_regime)

GRADE_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3}


def quarter_from_end(period_end: str) -> str:
    d = pd.to_datetime(period_end)
    return f"{d.year}Q{(d.month - 1) // 3 + 1}"


def downgrade_grade(grade: str) -> str:
    """F 缺失降级映射时的质量降级：A->B, B->C, C 保持 C（不降为 D，
    因为降级映射仍会产出 A- 级结论，D 表示无法形成判断）"""
    order = ["A", "B", "C", "D"]
    idx = order.index(grade) if grade in order else 3
    return order[min(idx + 1, 2)] if idx < 2 else "C"


def load_prev_regimes(conn) -> dict:
    """stock_code -> [(period_end, regime)]（升序）"""
    rows = conn.execute(
        "SELECT stock_code, period_end, structural_regime FROM qcfp_quarterly_structural"
    ).fetchall()
    prev_map = defaultdict(list)
    for r in rows:
        prev_map[r["stock_code"]].append((r["period_end"], r["structural_regime"]))
    for lst in prev_map.values():
        lst.sort()
    return dict(prev_map)


def get_prev_regime(prev_map: dict, stock_code: str, period_end: str):
    prev = None
    for pe0, rg in prev_map.get(stock_code, []):
        if pe0 < period_end:
            prev = rg
        else:
            break
    return prev


def build_merged(ih_df, chip_df, q_df, daily_df, settings) -> pd.DataFrame:
    c_df = build_c_factors(ih_df, settings)
    f_df = build_f_factors(chip_df, settings)
    p_df = build_p_factors(q_df, daily_df, settings)

    c_cols = ["stock_code", "stock_name", "quarter", "period_end", "source_period",
              "inst_ownership_pct_chg", "holder_quantity_chg_pct",
              "inst_participation_chg", "c_state", "c_confidence", "c_reason"]
    f_cols = ["stock_code", "period_end", "q_inst_flow_raw", "q_inst_flow_z",
              "q_ifa_zscore", "f_state", "f_reason"]
    p_cols = ["stock_code", "period_end", "q_return", "q_trend_score",
              "q_position_52w", "p_state", "p_flat_flag"]

    m = pd.merge(c_df[c_cols], f_df[f_cols], on=["stock_code", "period_end"], how="outer")
    m = pd.merge(m, p_df[p_cols], on=["stock_code", "period_end"], how="outer")
    m = m.sort_values(["stock_code", "period_end"]).reset_index(drop=True)
    return m, c_df, f_df, p_df


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF 季度结构引擎")
    parser.add_argument("--stock", help="只处理指定股票代码")
    parser.add_argument("--period-end", help="只处理指定季度（YYYY-MM-DD）")
    parser.add_argument("--dry-run", action="store_true", help="不写库，仅打印结果")
    args = parser.parse_args(argv)

    settings = load_qcfp_settings()
    from QCFP_MTF.decision.versions import MODEL_VERSION
    model_version = get(settings, "model.version", MODEL_VERSION)
    lag_days = int(get(settings, "institutional.disclosure_lag_days", 45))
    div_thr = float(get(settings, "structural.divergence.z_threshold", 1.0))
    log_name = f"structural_engine_{args.stock}" if args.stock else "structural_engine"
    logger = setup_logger("structural_engine", log_file=f"{log_name}.log", mode="w")
    logger.info("=== 季度结构引擎启动 ===")

    stocks = [args.stock] if args.stock else None
    ih_df = load_derived("quarterly_institutional_holdings_analysis")
    chip_df = load_derived("quarterly_chip_analysis")
    q_df = load_kline("quarterly", stocks=stocks)
    daily_df = load_kline("daily", stocks=stocks)

    # 有机构数据的股票池（C 是结构结论的前提）
    c_stocks = set(ih_df["stock_code"])
    all_stocks = sorted(set(q_df["stock_code"]) | c_stocks)
    skipped = [s for s in all_stocks if s not in c_stocks]
    if skipped:
        logger.info(f"无机构数据股票跳过（DATA_INSUFFICIENT）: {skipped}")

    if args.stock:
        ih_df = ih_df[ih_df["stock_code"] == args.stock]
        chip_df = chip_df[chip_df["stock_code"] == args.stock]
        q_df = q_df[q_df["stock_code"] == args.stock]
        daily_df = daily_df[daily_df["stock_code"] == args.stock]

    merged, c_df, f_df, p_df = build_merged(ih_df, chip_df, q_df, daily_df, settings)
    if merged.empty:
        logger.error("无可处理数据")
        return 1
    # 只处理有机构数据（C 是结构结论前提）的股票
    merged = merged[merged["stock_code"].isin(c_stocks)].reset_index(drop=True)
    if merged.empty:
        logger.error("机构数据股票范围内无可用数据")
        return 1
    if args.period_end:
        merged = merged[merged["period_end"] == args.period_end].reset_index(drop=True)
    if merged.empty:
        logger.error(f"指定季度 {args.period_end} 无数据")
        return 1

    # 标准化 Z-Score（个股滚动，用于背离）
    c_z = merged.groupby("stock_code")["inst_ownership_pct_chg"].transform(
        lambda s: rolling_zscore(s, 8, 3))
    p_z = merged.groupby("stock_code")["q_return"].transform(
        lambda s: rolling_zscore(s, 8, 3))
    f_z = merged["q_inst_flow_z"].astype(float)
    div = compute_divergence(c_z, f_z, p_z, threshold=div_thr)

    # 状态解析（使用库中已有状态作前一状态）
    conn = connect()
    try:
        prev_map = load_prev_regimes(conn)
        computed_prev: dict = {}  # 本次运行内：stock -> 上一季度状态
        regimes, methods = [], []
        for _, r in merged.iterrows():
            stock = r["stock_code"]
            if stock in computed_prev:
                prev = computed_prev[stock]
            else:
                prev = get_prev_regime(prev_map, stock, r["period_end"])
            rg, method = resolve_regime(r["c_state"], r["f_state"], r["p_state"], prev)
            computed_prev[stock] = rg
            regimes.append(rg)
            methods.append(method)
        merged["structural_regime"] = regimes
        merged["resolve_method"] = methods
        merged["core_score"] = [
            map_core_score(rg, settings) for rg in regimes
        ]

        # 数据质量继承
        labels = load_latest_quality_labels()
        label_map = {(r["stock_code"], r["data_type"]): r["grade"]
                     for _, r in labels.iterrows()}

        def _worst_grade(stock):
            grades = [label_map.get((stock, "institutional_holdings"), "D"),
                      label_map.get((stock, "quarterly_moneyflow"), "D"),
                      label_map.get((stock, "quarterly_kline"), "D")]
            return max(grades, key=lambda g: GRADE_ORDER.get(g, 3))

        merged["data_quality"] = [
            downgrade_grade(_worst_grade(s)) if m == "fallback_f_missing" else _worst_grade(s)
            for s, m in zip(merged["stock_code"], methods)
        ]

        # available_date = 季度末 + 披露滞后
        merged["available_date"] = (
            pd.to_datetime(merged["period_end"]) + pd.Timedelta(days=lag_days)
        ).dt.strftime("%Y-%m-%d")
        # 2.5 PIT 真实披露表：Config/qcfp_disclosure_dates.csv 覆盖推算日期
        overrides = load_disclosure_overrides()
        if overrides:
            merged["available_date_dt"] = pd.to_datetime(
                merged["available_date"], errors="coerce")
            merged = apply_disclosure_overrides(
                merged, overrides, period_col="period_end",
                avail_col="available_date_dt")
            merged["available_date"] = merged["available_date_dt"].dt.strftime(
                "%Y-%m-%d")
            logger.info(
                f"PIT 真实披露日覆盖：{len(overrides)} 条规则"
                f"（disclosure_mode=REAL）")
        else:
            logger.info(
                f"无披露日覆盖表，使用 period_end+{lag_days}d 估算"
                f"（disclosure_mode=ESTIMATED，PIT-C）")
        merged["quarter"] = merged["quarter"].fillna(
            merged["period_end"].map(quarter_from_end))

        # 汇总日志
        latest = merged.sort_values("period_end").groupby("stock_code").tail(1)
        logger.info("=== 最新季度结构状态 ===")
        for _, r in latest.iterrows():
            logger.info(
                f"  {r['stock_code']} {r['period_end']}: {r['structural_regime']} "
                f"(score={r['core_score']}, method={r['resolve_method']}, "
                f"C={r['c_state']} F={r['f_state']} P={r['p_state']}, dq={r['data_quality']})"
            )

        # 写报告
        report_root = get_report_root() / "structural"
        report_root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d")
        out_cols = ["stock_code", "stock_name", "quarter", "period_end", "available_date",
                    "inst_ownership_pct_chg", "holder_quantity_chg_pct",
                    "inst_participation_chg", "q_inst_flow_raw", "q_inst_flow_z",
                    "q_ifa_zscore", "q_return", "q_trend_score", "q_position_52w",
                    "c_state", "f_state", "p_state", "structural_regime",
                    "resolve_method", "core_score", "data_quality", "source_period"]
        for col in out_cols:
            if col not in merged.columns:
                merged[col] = None
        out = pd.concat([merged[out_cols], div], axis=1)
        fname = f"structural_{args.stock}_{stamp}" if args.stock else f"structural_{stamp}"
        csv_path = report_root / f"{fname}.csv"
        json_path = report_root / f"{fname}.json"
        out.to_csv(csv_path, index=False, encoding="utf-8-sig")
        json_path.write_text(
            json.dumps({"generated_at": stamp, "model_version": model_version,
                        "records": out.to_dict(orient="records")},
                       ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        logger.info(f"报告已保存: {csv_path}")

        # 写库
        if not args.dry_run:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            rows = []
            for _, r in out.iterrows():
                if r["structural_regime"] is None:
                    continue
                rows.append((
                    r["stock_code"], r["stock_name"], r["period_end"],
                    r["available_date"], r["inst_ownership_pct_chg"],
                    r["holder_quantity_chg_pct"], r["inst_participation_chg"],
                    r["q_inst_flow_raw"], r["q_inst_flow_z"], r["q_ifa_zscore"],
                    r["q_return"], r["q_trend_score"], r["q_position_52w"],
                    r["c_state"], r["f_state"], r["p_state"],
                    r["structural_regime"], r["core_score"], r["resolve_method"],
                    r["source_period"], model_version, r["data_quality"], now,
                ))
            conn.executemany(
                """INSERT OR REPLACE INTO qcfp_quarterly_structural
                   (stock_code, stock_name, period_end, available_date,
                    inst_ownership_pct_chg, holder_quantity_chg_pct,
                    inst_participation_chg, q_inst_flow_raw, q_inst_flow_z,
                    q_ifa_zscore, q_return, q_trend_score, q_position_52w,
                    c_state, f_state, p_state, structural_regime, core_score,
                    resolve_method, source_period, model_version, data_quality, update_time)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                rows,
            )
            conn.commit()
            logger.info(f"已 UPSERT {len(rows)} 行到 qcfp_quarterly_structural")
        else:
            logger.info("--dry-run 模式：未写库")
    finally:
        conn.close()

    logger.info("structural_engine 完成 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
