#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF P0.8 —— 数据覆盖度审计
逐表 × 逐股票统计行数、时间范围、周期完整度，输出 CSV/JSON 报告。
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

from QCFP_MTF.common.calendar import TradingCalendar
from QCFP_MTF.common.logger import setup_logger
from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.config.settings import get, load_qcfp_settings
from QCFP_MTF.data.loader import (SOURCE_TABLE, get_table_date_range, load_catalog,
                                  load_kline, load_stock_list)

PERIOD_OF = {
    "daily_kline": "daily",
    "weekly_kline": "weekly",
    "monthly_kline": "monthly",
    "quarterly_kline": "quarterly",
}


def _period_completeness(data_type: str, df: pd.DataFrame, cal: TradingCalendar):
    """周期完整度：数据自身首末区间内，实际周期数 / 应有周期数"""
    if df.empty or "date" not in df.columns:
        return None, None
    dts = pd.to_datetime(df["date"], errors="coerce").dropna()
    if dts.empty:
        return None, None
    first, last = dts.min().date(), dts.max().date()
    if data_type in PERIOD_OF:
        period = PERIOD_OF[data_type]
        buckets = cal.split_periods(first, last, period)
        labels = {cal.period_label(d, period) for d in dts.dt.date}
        expected = len(buckets)
        actual = len(labels & {b[0] for b in buckets})
        return actual, expected
    if data_type == "institutional_holdings":
        periods = df["period_text"].dropna().unique()
        return len(periods), len(periods)  # 已有季度数
    return len(df), None


def build_audit(cal: TradingCalendar, stocks: pd.DataFrame, catalog: dict) -> pd.DataFrame:
    rows = []
    all_stocks = set(stocks["stock_code"]) if "stock_code" in stocks.columns else set()
    for data_type, df in catalog.items():
        if df.empty:
            for code in sorted(all_stocks):
                rows.append(_audit_row(code, data_type, 0, None, None, 0, 0, "无数据"))
            continue
        if data_type == "idx_hist":
            first, last = get_table_date_range(SOURCE_TABLE[data_type])
            rows.append(_audit_row("IDX", data_type, len(df), first, last, None, None, ""))
            continue
        for code, g in df.groupby("stock_code", dropna=False):
            code = str(code)
            dts = pd.to_datetime(g["date"], errors="coerce").dropna() if "date" in g.columns else pd.Series(dtype="datetime64[ns]")
            first = dts.min().strftime("%Y-%m-%d") if len(dts) else None
            last = dts.max().strftime("%Y-%m-%d") if len(dts) else None
            actual, expected = _period_completeness(data_type, g, cal)
            note = ""
            if expected:
                ratio = actual / expected
                note = f"周期完整度 {actual}/{expected}"
                if ratio < 0.95:
                    note += "（不足）"
            rows.append(_audit_row(code, data_type, len(g), first, last, actual, expected, note))

    df_out = pd.DataFrame(rows)
    # 股票池中完全没有数据的表
    for code in sorted(all_stocks):
        for data_type in catalog:
            if data_type == "idx_hist":
                continue
            if not ((df_out["stock_code"] == code) & (df_out["data_type"] == data_type)).any():
                df_out = pd.concat([df_out, pd.DataFrame([_audit_row(code, data_type, 0, None, None, 0, 0, "无数据")])], ignore_index=True)
    return df_out.sort_values(["stock_code", "data_type"]).reset_index(drop=True)


def _audit_row(code, data_type, rows, first, last, actual, expected, note):
    return {
        "stock_code": code,
        "data_type": data_type,
        "rows": rows,
        "first_date": first,
        "last_date": last,
        "actual_periods": actual,
        "expected_periods": expected,
        "note": note,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF 数据覆盖度审计")
    parser.add_argument("--stock", help="只审计指定股票代码")
    parser.add_argument("--output-dir", help="报告输出目录（默认 Report/QCFP_MTF/audit）")
    args = parser.parse_args(argv)

    settings = load_qcfp_settings()
    report_root = get_report_root()
    out_dir = Path(args.output_dir) if args.output_dir else report_root / get(settings, "output.audit_subdir", "audit")
    out_dir.mkdir(parents=True, exist_ok=True)

    log_name = f"audit_coverage_{args.stock}" if args.stock else "audit_coverage"
    logger = setup_logger("audit_coverage", log_file=f"{log_name}.log", mode="w")
    logger.info("开始数据覆盖度审计 ...")

    stocks = load_stock_list()
    if args.stock:
        stocks = stocks[stocks["stock_code"] == args.stock].reset_index(drop=True)
    cal = TradingCalendar.from_db()
    catalog = load_catalog()
    audit = build_audit(cal, stocks, catalog)

    stamp = datetime.now().strftime("%Y%m%d")
    fname = f"coverage_report_{args.stock}_{stamp}" if args.stock else f"coverage_report_{stamp}"
    csv_path = out_dir / f"{fname}.csv"
    json_path = out_dir / f"{fname}.json"
    audit.to_csv(csv_path, index=False, encoding="utf-8-sig")
    json_path.write_text(
        json.dumps({"generated_at": stamp,
                    "model_version": get(settings, "model.version"),
                    "records": audit.to_dict(orient="records")},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 汇总
    per_table = audit.groupby("data_type").agg(
        rows=("rows", "sum"), stocks_with_data=("stock_code", lambda s: (audit.loc[s.index, "rows"] > 0).sum())
    )
    logger.info("=== 按表汇总 ===")
    for t, r in per_table.iterrows():
        logger.info(f"  {t}: {int(r['rows'])} 行, {int(r['stocks_with_data'])} 只股票")
    no_data = audit[(audit["rows"] == 0) & (audit["stock_code"] != "IDX")]
    if len(no_data):
        logger.info(f"=== 缺失数据 {len(no_data)} 项 ===")
        for _, r in no_data.iterrows():
            logger.info(f"  {r['stock_code']} / {r['data_type']}: 无数据")
    logger.info(f"覆盖度报告已保存: {csv_path}")
    logger.info("audit_coverage 完成 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
