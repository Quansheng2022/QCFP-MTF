#!/usr/bin/env python
# coding: utf-8
"""QCFP_MTF Research Outcome 异步回填（Runtime Evidence Wiring：第 4 项）

每日运行：Decision Ledger → 查哪些 horizon 已成熟 → Market Data as-of
evaluation_time → 计算 Outcome → INSERT ONLY（绝不 UPDATE Decision Row）。

覆盖 outcome_type：TRADE / NO_TRADE / ABSTAIN（Missed Opportunity /
Correct Abstention / False Participation 分析基础）。

用法：
    python Core/QCFP_MTF/scripts/backfill_research_outcomes.py \
        [--horizons 5D,20D,60D] [--limit N]
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.common.db import connect
from QCFP_MTF.common.logger import setup_logger
from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.research.research_outcome import outcome_ledger_append, \
    research_outcome


def _horizon_days(horizon: str) -> int:
    h = str(horizon or "").upper()
    if h.endswith("D"):
        return int(h[:-1])
    if h.endswith("W"):
        return int(h[:-1]) * 7
    if h.endswith("M"):
        return int(h[:-1]) * 30
    return int(h or "0")


def _kline_prices(conn, stock, decision_date, horizon_days):
    """决策日后 N 天窗口内的收盘价序列（as-of，不含未来泄露）。"""
    start = str(decision_date)[:10]
    rows = conn.execute(
        "SELECT date AS trade_date, close, high, low "
        "FROM hk_hist_daily_kline "
        "WHERE stock_code=? AND date>? ORDER BY date",
        (stock, start)).fetchall()
    return [dict(r) for r in rows]


def compute_outcome(rows, horizon_days):
    """从 as-of 价格序列计算 future_return / mfe / mae /
    wave_peak_return；不足窗口 → 未成熟（返回 None）。"""
    if not rows:
        return None
    target_idx = horizon_days if horizon_days > 0 else len(rows)
    horizon_rows = rows[:target_idx]
    if len(horizon_rows) < max(1, horizon_days):
        return None
    entry = float(rows[0]["close"] or 0.0)
    if entry <= 0:
        return None
    exit_price = float(horizon_rows[-1]["close"] or 0.0)
    future_return = (exit_price - entry) / entry
    mfe = max((float(r["high"] or entry) - entry) / entry
              for r in horizon_rows)
    mae = min((float(r["low"] or entry) - entry) / entry
              for r in horizon_rows)
    peak = max(float(r["high"] or entry) for r in horizon_rows)
    wave_peak_return = (peak - entry) / entry
    return {
        "evaluation_time": str(horizon_rows[-1]["trade_date"])[:10],
        "horizon_end": str(horizon_rows[-1]["trade_date"])[:10],
        "entry_reference_price": entry,
        "exit_reference_price": exit_price,
        "future_return": round(future_return, 6),
        "mfe": round(mfe, 6),
        "mae": round(mae, 6),
        "wave_peak_return": round(wave_peak_return, 6),
    }


def backfill_outcomes(conn, horizons=("5D", "20D", "60D"),
                      limit=None, today=None, release_id=None,
                      since=None) -> dict:
    """回填已成熟决策的 Outcome；INSERT ONLY。

    P0-1：Daily Runner 按 release_id + since 收口，避免每天全表扫描
    82k 历史决策；不传时保留旧行为（全量）。"""
    from QCFP_MTF.research.research_outcome import \
        ensure_research_outcome_table
    ensure_research_outcome_table(conn)
    today = today or datetime.now().strftime("%Y-%m-%d")
    inserted, skipped, errors = 0, 0, []
    sql = ("SELECT decision_id, stock_code, decision_date, final_target, "
           "json_extract(context,'$.release_identity.release_id') "
           "AS release_id FROM qcfp_decision_ledger "
           "WHERE status='ACTIVE'")
    params = []
    if release_id:
        sql += " AND json_extract(context,'$.release_identity.release_id')=?"
        params.append(release_id)
    if since:
        sql += " AND decision_date>=?"
        params.append(since)
    sql += " ORDER BY decision_date DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"
    decisions = conn.execute(sql, params).fetchall()
    existing = {r[0] for r in conn.execute(
        "SELECT outcome_id FROM qcfp_research_outcome")}
    for d in decisions:
        for horizon in horizons:
            days = _horizon_days(horizon)
            oid = f"OC-{d['decision_id']}-{horizon}"
            if oid in existing:
                skipped += 1
                continue
            rows = _kline_prices(conn, d["stock_code"], d["decision_date"],
                                 days)
            calc = compute_outcome(rows, days)
            if calc is None:
                skipped += 1
                continue
            if calc["horizon_end"] > today:
                skipped += 1
                continue
            outcome_type = "TRADE" if float(d["final_target"] or 0.0) \
                > 1e-9 else "NO_TRADE"
            missed = outcome_type == "NO_TRADE" \
                and calc["future_return"] > 0.02
            outcome = research_outcome(
                d["decision_id"], d["release_id"] or "", d["stock_code"],
                d["decision_date"], horizon,
                future_return=calc["future_return"],
                mfe=calc["mfe"], mae=calc["mae"],
                wave_peak_return=calc["wave_peak_return"],
                missed_opportunity=missed,
                outcome_type=outcome_type,
                outcome_id=oid,
                evaluation_time=calc["evaluation_time"],
                horizon_end=calc["horizon_end"],
                entry_reference_price=calc["entry_reference_price"],
                exit_reference_price=calc["exit_reference_price"],
                source_data_snapshot_id=f"kline:{calc['horizon_end']}",
                created_at=today)
            try:
                inserted += outcome_ledger_append(conn, outcome)
                existing.add(oid)
            except ValueError as exc:
                errors.append({"decision_id": d["decision_id"],
                               "horizon": horizon, "error": str(exc)})
    conn.commit()
    return {"horizons": list(horizons),
            "inserted": inserted,
            "skipped": skipped,
            "errors": errors,
            "rule": "Outcome 只追加、future-aware、"
                    "INSERT ONLY（绝不 UPDATE Decision Row）"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="QCFP-MTF Research Outcome 异步回填")
    parser.add_argument("--horizons", default="5D,20D,60D")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)
    logger = setup_logger("backfill_research_outcomes",
                          log_file="backfill_research_outcomes.log",
                          mode="a")
    horizons = tuple(h.strip() for h in args.horizons.split(",") if h.strip())
    conn = connect()
    try:
        # 显式 Bootstrap（Production schema 由 SQL 迁移拥有）
        from QCFP_MTF.research.research_outcome import \
            ensure_research_outcome_table
        ensure_research_outcome_table(conn)
        result = backfill_outcomes(conn, horizons, limit=args.limit)
    finally:
        conn.close()
    logger.info(f"backfill: inserted={result['inserted']} "
                f"skipped={result['skipped']} errors={len(result['errors'])}")
    print(f"Outcome backfill: inserted={result['inserted']} "
          f"skipped={result['skipped']} errors={len(result['errors'])}")
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
