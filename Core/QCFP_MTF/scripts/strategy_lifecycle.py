#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF 2.7 —— Strategy Lifecycle CLI

Development → Research → Validation → Candidate → Shadow → Paper →
Production → Retired；生产变更必须走
    Candidate → Ablation → OOS → Shadow → Approval → Production。

用法：
    python Core/QCFP_MTF/scripts/strategy_lifecycle.py list
    python Core/QCFP_MTF/scripts/strategy_lifecycle.py register V1 --rule GOV-2.5.0
    python Core/QCFP_MTF/scripts/strategy_lifecycle.py promote V1 production
    python Core/QCFP_MTF/scripts/strategy_lifecycle.py retire V1 --date 2026-12-31
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


def _row(v, status=None):
    return (v["version"], v.get("data_version", "1.0"),
            v.get("feature_version", ""), v.get("rule_version", ""),
            v.get("parameter_version", ""),
            status or v.get("approval_status", "development"),
            v.get("effective_date", ""), v.get("retirement_date", ""),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Strategy Lifecycle CLI")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    reg = sub.add_parser("register")
    reg.add_argument("version")
    reg.add_argument("--data-version", default="1.0")
    reg.add_argument("--feature-version", default="")
    reg.add_argument("--rule-version", default="GOV-2.5.0")
    reg.add_argument("--parameter-version", default="")
    pro = sub.add_parser("promote")
    pro.add_argument("version")
    pro.add_argument("status",
                     choices=["research", "validation", "candidate",
                              "shadow", "paper", "production", "retired"])
    pro.add_argument("--date", default="")
    ret = sub.add_parser("retire")
    ret.add_argument("version")
    ret.add_argument("--date", default="")
    args = p.parse_args(argv)
    conn = connect()
    try:
        if args.cmd == "list":
            rows = conn.execute(
                "SELECT version, rule_version, approval_status, "
                "effective_date, retirement_date FROM "
                "qcfp_strategy_lifecycle ORDER BY id").fetchall()
            for r in rows:
                print(f"{r['version']} [{r['approval_status']}] "
                      f"rule={r['rule_version']} "
                      f"eff={r['effective_date'] or '—'} "
                      f"ret={r['retirement_date'] or '—'}")
            return 0
        if args.cmd == "register":
            exists = conn.execute(
                "SELECT 1 FROM qcfp_strategy_lifecycle WHERE version=?",
                (args.version,)).fetchone()
            if exists:
                print(f"❌ 版本 {args.version} 已存在")
                return 1
            v = {"version": args.version, "data_version": args.data_version,
                 "feature_version": args.feature_version,
                 "rule_version": args.rule_version,
                 "parameter_version": args.parameter_version,
                 "approval_status": "development",
                 "effective_date": "", "retirement_date": ""}
            conn.execute(
                "INSERT INTO qcfp_strategy_lifecycle "
                "(version, data_version, feature_version, rule_version, "
                "parameter_version, approval_status, effective_date, "
                "retirement_date, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                _row(v))
            conn.commit()
            print(f"✅ 注册 {args.version}（development）")
            return 0
        if args.cmd == "promote":
            from QCFP_MTF.governance.lifecycle import (LIFECYCLE_ORDER,
                                                       StrategyLifecycleError)
            r = conn.execute(
                "SELECT * FROM qcfp_strategy_lifecycle WHERE version=?",
                (args.version,)).fetchone()
            if not r:
                print(f"❌ 未知版本 {args.version}")
                return 1
            cur = r["approval_status"]
            if LIFECYCLE_ORDER.index(args.status) < LIFECYCLE_ORDER.index(cur):
                print("❌ 禁止回退生命周期状态")
                return 1
            eff = args.date if args.status == "production" else r["effective_date"]
            conn.execute(
                "UPDATE qcfp_strategy_lifecycle SET approval_status=?, "
                "effective_date=?, updated_at=? WHERE version=?",
                (args.status, eff, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 args.version))
            conn.commit()
            print(f"✅ {args.version} → {args.status}")
            return 0
        if args.cmd == "retire":
            conn.execute(
                "UPDATE qcfp_strategy_lifecycle SET approval_status='retired', "
                "retirement_date=?, updated_at=? WHERE version=?",
                (args.date or datetime.now().strftime("%Y-%m-%d"),
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S"), args.version))
            conn.commit()
            print(f"✅ {args.version} → retired")
            return 0
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
