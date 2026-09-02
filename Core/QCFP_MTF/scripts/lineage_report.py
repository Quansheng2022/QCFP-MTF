#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF 2.8 —— Data Lineage Report（数据血缘报告）

从 qcfp_decision_ledger 反向追溯到各输入表（原始数据 + 可用时间 + 快照），
输出完整血缘链与 lineage_hash。

用法：
    python Core/QCFP_MTF/scripts/lineage_report.py --stock 01951
        [--date 2026-08-21]
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
from QCFP_MTF.data.lineage import build_lineage, lineage_to_md
from QCFP_MTF.decision.decision_ledger import compute_data_snapshot_id


RAW_TABLES = (
    ("hk_hist_daily_kline", "moomoo/openD"),
    ("hk_hist_daily_moneyflow", "futu/moomoo"),
    ("hk_hist_institutional_holdings", "hkex/ccass"),
    ("qcfp_quarterly_structural", "qcfp_p1"),
    ("qcfp_monthly_behavior", "qcfp_p2"),
    ("qcfp_weekly_tactical", "qcfp_p3"),
    ("qcfp_daily_tactical", "qcfp_l4"),
)


def _latest_available(conn, table, stock, date, date_col):
    try:
        r = conn.execute(
            f"SELECT MAX({date_col}) AS d FROM {table} "
            f"WHERE stock_code=? AND {date_col}<=?",
            (stock, date)).fetchone()
        return r["d"] if r else ""
    except Exception:
        return ""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF 数据血缘报告")
    parser.add_argument("--stock", required=True)
    parser.add_argument("--date", default=None)
    args = parser.parse_args(argv)
    logger = setup_logger("lineage_report", log_file="lineage_report.log",
                          mode="a")
    from QCFP_MTF.scripts.dss_report import _latest_decision
    conn = connect()
    try:
        date = args.date or _latest_decision(conn, args.stock)
        snap_id = compute_data_snapshot_id(conn)
        ledger = conn.execute(
            "SELECT decision_id, run_id, input_fingerprint, data_snapshot_id "
            "FROM qcfp_decision_ledger WHERE stock_code=? AND decision_date=?"
            " AND status='ACTIVE' ORDER BY created_at DESC LIMIT 1",
            (args.stock, date)).fetchone()
        raw = []
        for table, src in RAW_TABLES:
            date_col = "date" if table.startswith("hk_") else (
                "available_date" if "structural" in table else (
                    "month_end" if "monthly" in table else (
                        "week_end" if "weekly" in table else "trade_date")))
            avail = _latest_available(conn, table, args.stock, date, date_col)
            raw.append((table, src, snap_id, avail, "PIT_CHK"))
        # 变换链：L1-L4 引擎 → 指标 → 特征
        transforms = [
            ("qcfp_quarterly_structural", "p1_v48", ("hk_hist_institutional_holdings",)),
            ("qcfp_monthly_behavior", "p2_v48", ("hk_hist_monthly_kline",)),
            ("qcfp_weekly_tactical", "p3_v48", ("hk_hist_weekly_kline",)),
            ("qcfp_daily_tactical", "l4_v48", ("hk_hist_daily_kline",)),
        ]
        indicators = [
            ("structural_regime", "v48", ("qcfp_quarterly_structural",)),
            ("monthly_behavior_state", "v48", ("qcfp_monthly_behavior",)),
            ("tactical_signal", "v48", ("qcfp_weekly_tactical",)),
            ("daily_state", "v48", ("qcfp_daily_tactical",)),
        ]
        features = [
            ("institutional_permission", "v48",
             ("structural_regime", "monthly_behavior_state")),
            ("final_target", "v50", ("institutional_permission",
                                     "tactical_signal", "daily_state")),
        ]
    finally:
        conn.close()
    lineage = build_lineage(
        decision_id=(ledger["decision_id"] if ledger
                     else f"{args.stock}_{date}"),
        stock_code=args.stock, decision_date=date,
        raw_sources=raw, transforms=transforms,
        indicators=indicators, features=features)
    output = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stock": args.stock, "decision_date": date,
        "data_snapshot_id": snap_id,
        "ledger": dict(ledger) if ledger else None,
        "lineage": lineage.as_dict(),
    }
    report_root = get_report_root() / "lineage"
    report_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    json_path = report_root / f"lineage_{args.stock}_{stamp}.json"
    json_path.write_text(json.dumps(output, ensure_ascii=False, indent=2,
                                    default=str), encoding="utf-8")
    md = lineage_to_md(lineage)
    md_path = report_root / f"lineage_{args.stock}_{stamp}.md"
    md_path.write_text(md, encoding="utf-8")
    print(md)
    logger.info(f"{args.stock} {date} lineage_hash={lineage.lineage_hash}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
