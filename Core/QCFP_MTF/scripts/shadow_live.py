#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF 2.6 —— Live Shadow（实时影子决策，不提交真实订单）

每日真实运行：
    当日数据 → PIT Evidence → Decision Engine → Decision Certificate
    → 记录理论成交（模拟成交，不提交订单）→ 输出"今日决策/目标/模拟成交"

同时做 Model Drift 监控：实时 Shadow 的 Permission 分布 vs 回测基线，
偏差超阈值 → REGIME_DRIFT。

用法：python Core/QCFP_MTF/scripts/shadow_live.py --stock 01951
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
from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.config.settings import load_qcfp_settings
from QCFP_MTF.decision.decision_certificate import build_certificate
from QCFP_MTF.decision.engine import evaluate
from QCFP_MTF.shadow.drift import distribution_drift, drift_report


def _permission_distribution(conn, run_id=None):
    sql = ("SELECT institutional_permission, COUNT(*) AS n "
           "FROM qcfp_decision_ledger")
    params = []
    if run_id:
        sql += " WHERE run_id=?"
        params.append(run_id)
    sql += " GROUP BY institutional_permission"
    rows = conn.execute(sql, params).fetchall()
    total = sum(r["n"] for r in rows) or 1
    return {r["institutional_permission"]: round(r["n"] / total, 4)
            for r in rows}


def _distribution(conn, column, run_id=None):
    sql = f"SELECT {column}, COUNT(*) AS n FROM qcfp_decision_ledger"
    params = []
    if run_id:
        sql += " WHERE run_id=?"
        params.append(run_id)
    sql += f" GROUP BY {column}"
    rows = conn.execute(sql, params).fetchall()
    total = sum(r["n"] for r in rows) or 1
    return {str(r[column]): round(r["n"] / total, 4) for r in rows}


def _transition_distribution(conn, run_id=None):
    sql = ("SELECT previous_fsm_state, next_fsm_state, COUNT(*) AS n "
           "FROM qcfp_decision_ledger")
    params = []
    if run_id:
        sql += " WHERE run_id=?"
        params.append(run_id)
    sql += " GROUP BY previous_fsm_state, next_fsm_state"
    rows = conn.execute(sql, params).fetchall()
    total = sum(r["n"] for r in rows) or 1
    return {f"{r['previous_fsm_state']}→{r['next_fsm_state']}":
            round(r["n"] / total, 4) for r in rows}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF Live Shadow")
    parser.add_argument("--stock", required=True)
    parser.add_argument("--threshold", type=float, default=0.15)
    args = parser.parse_args(argv)
    settings = load_qcfp_settings()

    from QCFP_MTF.scripts.dss_report import _latest_decision, _row
    conn = connect()
    try:
        date = _latest_decision(conn, args.stock)
        row = _row(conn, args.stock, date) if date else None
        latest = conn.execute(
            "SELECT run_id, previous_fsm_state, previous_position "
            "FROM qcfp_decision_ledger WHERE stock_code=? "
            "AND decision_date=? AND status='ACTIVE' "
            "ORDER BY created_at DESC, id DESC LIMIT 1",
            (args.stock, date or "")).fetchone()
        # 漂移：回测基线 = 全部台账分布；实时 = 最新 run 分布
        baseline = {
            "permission_dist": _permission_distribution(conn),
            "setup_dist": _distribution(conn, "setup_type"),
            "fsm_transition_dist": _transition_distribution(conn),
        }
        latest_run = conn.execute(
            "SELECT MAX(id) FROM qcfp_decision_ledger").fetchone()[0]
        live_run = conn.execute(
            "SELECT run_id FROM qcfp_decision_ledger WHERE id=?",
            (latest_run,)).fetchone()
        live_run_id = live_run["run_id"] if live_run else None
        live_dist = {
            "permission_dist": _permission_distribution(conn, live_run_id),
            "setup_dist": _distribution(conn, "setup_type", live_run_id),
            "fsm_transition_dist": _transition_distribution(conn, live_run_id),
        }
    finally:
        conn.close()
    if not row:
        print(f"❌ {args.stock} 无决策数据")
        return 1
    prev_fsm = latest["previous_fsm_state"] if latest else "FLAT"
    prev_pos = float(latest["previous_position"] or 0.0) if latest else 0.0
    snap = evaluate(dict(row), prev_fsm, prev_pos, settings,
                    run_id=f"live_shadow_{datetime.now():%Y%m%d_%H%M%S}")
    cert = build_certificate(snap)
    drift = drift_report(baseline, live_dist,
                         thresholds={"distribution": args.threshold})
    drift_flag = drift["overall"] != "NORMAL"

    first_screen = [
        f"{args.stock}　{date}", "",
        f"Institutional　{snap.institutional_state}",
        f"Permission　{snap.institutional_permission}",
        f"Swing Setup　{snap.setup_type or 'NONE'}",
        f"Risk　{row.get('risk_level') or '—'}",
        f"FSM　{snap.prev_fsm_state} → {snap.next_fsm_state}",
        f"Previous Position　{snap.previous_position * 100:.0f}%",
        f"Final Target　{snap.target_position * 100:.0f}%",
        f"ACTION　{snap.position_class}",
        "Why?", *[f"{i}. {c}" for i, c in enumerate(
            (snap.primary_reason,) + tuple(snap.secondary_reasons), 1)],
    ]
    out = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "first_screen": first_screen,
        "certificate": cert.as_dict(),
        "simulated_fill": {
            "assumption": "T+1 周收盘确认成交（Next Close 口径，BASE 全额成交）",
            "orders_submitted": False,
        },
        "drift": {
            "flag": drift["overall"] if drift_flag else "NORMAL",
            "metrics": drift["metrics"],
            "drifted": drift["drifted"],
            "baseline": baseline,
            "live": live_dist,
            "threshold": args.threshold,
        },
    }
    out_dir = get_report_root() / "shadow" / "live"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    (out_dir / f"live_shadow_{args.stock}_{stamp}.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")
    print("\n".join(first_screen))
    print(f"\nDRIFT: {out['drift']['flag']}"
          f"（drifted={out['drift']['drifted']}）")
    print(f"Live Shadow 已保存: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
