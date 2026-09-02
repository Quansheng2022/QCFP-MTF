#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF 2.5 —— Audit Report（审计报告，报告三拆分之一）

回答"这次决策能否被第三方复现"：从决策台账 qcfp_decision_ledger 读取
七元审计身份 / 哈希 / 规则链 / 证据 as-of / 前后仓位 / 约束 / 治理核验。

用法：python Core/QCFP_MTF/scripts/audit_report.py --stock 01951 [--date 2026-08-21]
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.common.db import connect
from QCFP_MTF.common.paths import get_report_root


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF Audit Report")
    parser.add_argument("--stock", required=True)
    parser.add_argument("--date", default=None)
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args(argv)
    conn = connect()
    try:
        if args.date is None:
            r = conn.execute(
                "SELECT MAX(decision_date) FROM qcfp_decision_ledger "
                "WHERE stock_code=?", (args.stock,)).fetchone()[0]
            args.date = r
        if args.run_id:
            rows = conn.execute(
                "SELECT * FROM qcfp_decision_ledger "
                "WHERE stock_code=? AND decision_date=? AND run_id=? "
                "AND status='ACTIVE'",
                (args.stock, args.date, args.run_id)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM qcfp_decision_ledger "
                "WHERE stock_code=? AND decision_date=? AND status='ACTIVE' "
                "ORDER BY created_at DESC, id DESC LIMIT 1",
                (args.stock, args.date)).fetchall()
    finally:
        conn.close()
    if not rows:
        print(f"❌ 台账无 {args.stock}/{args.date} 的 ACTIVE 决策")
        return 1
    r = rows[0]
    lines = [f"# QCFP-MTF Audit Report　{args.stock}　{args.date}\n",
             "## 审计身份（七元组）\n",
             "| 维度 | 值 |", "| :-- | :-- |",
             f"| decision_id | `{r['decision_id']}` |",
             f"| run_id | `{r['run_id']}` |",
             f"| input_fingerprint | `{r['input_fingerprint']}` |",
             f"| data_snapshot_id | `{r['data_snapshot_id']}` |",
             f"| data_version | `{r['data_version']}` |",
             f"| settings_hash | `{r['settings_hash']}` |",
             f"| model_version | `{r['model_version']}` |",
             f"| rule_version | `{r['rule_version']}` |",
             f"| schema_version | `{r['schema_version']}` |\n",
             "## 决策链\n",
             "| 环节 | 值 |", "| :-- | :-- |",
             f"| Institutional | {r['institutional_state']} → "
             f"{r['institutional_permission']}（cap {r['permission_cap']}） |",
             f"| Exit | {r['exit_event']}：{r['exit_reason']}"
             f"（L{r['exit_severity']}） |",
             f"| Setup | {r['setup_type']} |",
             f"| Participation | {r['participation_mode']}"
             f" ≤ {r['participation_cap']}｜类别 {r['position_class']} |",
             f"| FSM | {r['previous_fsm_state']} → {r['next_fsm_state']}"
             f"（基准 {r['base_fsm_state']}） |",
             f"| Position | {r['previous_position']} → "
             f"raw {r['raw_target']} → final {r['final_target']}"
             f"（约束 {r['permission_constraint_applied']}） |",
             f"| Rules | `{r['override_rule_ids']}` |",
             f"| 决策原因 | {r['primary_reason']}（{r['secondary_reasons']}） |",
             f"| TQS | {r['trade_quality']}（{r['trade_quality_band']}） |\n",
             "## 治理核验\n",
             "| 项 | 值 |", "| :-- | :-- |",
             f"| Feature Manifest | `{r['feature_manifest_hash']}` |",
             f"| Status | {r['status']}"
             f"{'（superseded_by ' + r['superseded_by'] + '）' if r['superseded_by'] else ''} |",
             f"| PIT / 数据质量 | {r['pit_grade']} / {r['data_quality']} |",
             f"| created_at | {r['created_at']} |\n"]
    out_dir = get_report_root() / "audit"
    out_dir.mkdir(parents=True, exist_ok=True)
    md = "\n".join(lines)
    (out_dir / f"{args.stock}_audit_{args.date}.md").write_text(
        md, encoding="utf-8")
    (out_dir / f"{args.stock}_audit_{args.date}.json").write_text(
        json.dumps({k: r[k] for k in r.keys()}, ensure_ascii=False,
                   indent=2, default=str), encoding="utf-8")
    print(f"Audit Report 已生成: {out_dir / f'{args.stock}_audit_{args.date}.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
