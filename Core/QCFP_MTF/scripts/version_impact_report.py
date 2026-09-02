#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF 2.8 —— Version Impact Report（版本变更影响分析）

同一批决策，对比旧/新版本：Decision/Permission/Wave/FSM/Position/Exit/
P&L/Risk 差异 + Decision Flip Rate。

用法（DB 台账两版本对比）：
    python Core/QCFP_MTF/scripts/version_impact_report.py \
        --stock 01951 [--old-run shadow_xxx] [--new-run shadow_yyy]

用法（JSON 快照文件对比）：
    python Core/QCFP_MTF/scripts/version_impact_report.py \
        --old-file old.json --new-file new.json

快照 JSON：{decision_id: {field: value, ...}}（DecisionSnapshot as_dict）。
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
from QCFP_MTF.governance.version_impact import impact_to_md, version_impact


def _runs(conn, stock, old_run=None, new_run=None):
    if old_run and new_run:
        return old_run, new_run
    rows = conn.execute(
        "SELECT DISTINCT run_id FROM qcfp_decision_ledger "
        "WHERE stock_code=? AND status='ACTIVE' "
        "ORDER BY created_at DESC LIMIT 2", (stock,)).fetchall()
    ids = [r["run_id"] for r in rows]
    if len(ids) < 2:
        return None, None
    return (new_run or ids[1]), (old_run or ids[0])


def _snapshots(conn, stock, run_id):
    rows = conn.execute(
        "SELECT decision_id, institutional_permission, setup_type, "
        "exit_event, previous_fsm_state, next_fsm_state, previous_position, "
        "final_target, primary_reason FROM qcfp_decision_ledger "
        "WHERE stock_code=? AND run_id=? AND status='ACTIVE'",
        (stock, run_id)).fetchall()
    return {r["decision_id"]: dict(r) for r in rows}


def _load_file(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {"snapshots": data}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF 版本影响分析")
    parser.add_argument("--stock", default="01951")
    parser.add_argument("--old-run", default=None)
    parser.add_argument("--new-run", default=None)
    parser.add_argument("--old-file", default=None)
    parser.add_argument("--new-file", default=None)
    args = parser.parse_args(argv)
    logger = setup_logger("version_impact_report",
                          log_file="version_impact_report.log", mode="a")
    if args.old_file and args.new_file:
        old_snaps, new_snaps = _load_file(args.old_file), \
            _load_file(args.new_file)
        old_label, new_label = Path(args.old_file).stem, \
            Path(args.new_file).stem
    else:
        conn = connect()
        try:
            old_run, new_run = _runs(conn, args.stock, args.old_run,
                                     args.new_run)
            if not old_run or not new_run:
                print(f"❌ {args.stock} 台账不足两个 run")
                return 1
            old_snaps = _snapshots(conn, args.stock, old_run)
            new_snaps = _snapshots(conn, args.stock, new_run)
            old_label, new_label = old_run, new_run
        finally:
            conn.close()
    impact = version_impact(old_snaps, new_snaps,
                            old_version=old_label, new_version=new_label)
    output = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stock": args.stock,
        "old_version": old_label, "new_version": new_label,
        "impact": impact.as_dict(),
    }
    report_root = get_report_root() / "version_impact"
    report_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    json_path = report_root / f"version_impact_{args.stock}_{stamp}.json"
    json_path.write_text(json.dumps(output, ensure_ascii=False, indent=2,
                                    default=str), encoding="utf-8")
    md = impact_to_md(impact)
    md_path = report_root / f"version_impact_{args.stock}_{stamp}.md"
    md_path.write_text(md, encoding="utf-8")
    print(md)
    logger.info(f"{args.stock} {old_label}→{new_label} "
                f"flip={impact.flip_rate:.1%} n={impact.n_decisions}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
