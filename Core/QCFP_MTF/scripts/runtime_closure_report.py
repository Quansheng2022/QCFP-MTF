#!/usr/bin/env python
# coding: utf-8
"""Runtime Closure Report（C2/C3：连续 Shadow/Paper 证据产物）

从 Rolling Evidence Store（qcfp_runtime_evidence_daily）读取
Verified Evidence projection，产出 Closure 验收 artifact：
    shadow_20d_qualification.json
    shadow_20d_runtime_evidence.json
    shadow_20d_replay_summary.json
    shadow_terminal_state_distribution.json

本模块只读 Evidence + 调 Qualification Gate，不计算任何
Decision/Permission/Target/Risk/Wave。

用法：
    python Core/QCFP_MTF/scripts/runtime_closure_report.py \
        [--release MTR-CLOSURE-1] [--mode SHADOW] [--required-days 20]
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


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2,
                               default=str), encoding="utf-8")


def build_closure_report(conn, release_id, execution_mode,
                         required_days=20) -> dict:
    from QCFP_MTF.monitoring.runtime_evidence_store import (
        load_runtime_evidence_window, rolling_evidence_summary)
    from QCFP_MTF.governance.runtime_promotion_gate import \
        evaluate_decision_support_qualification, \
        evaluate_shadow_qualification
    rows = load_runtime_evidence_window(
        conn, release_id, execution_mode, "2000-01-01", "2999-12-31")
    rolling = rolling_evidence_summary(rows, required_days=required_days)
    gate = evaluate_shadow_qualification(rows,
                                         required_days=required_days)
    ds_gate = evaluate_decision_support_qualification(
        rows, shadow_days=required_days, outcome_days=required_days)
    window = [{
        "trade_date": r["trade_date"],
        "verdict": r["verdict"],
        "coverage": r["coverage"],
        "replay_eligible": r["replay_eligible"],
        "replay_exact": r["replay_exact"],
        "critical_replay_mismatch": r["critical_replay_mismatch"],
        "evidence_hash": r["evidence_hash"],
        "revision_no": r["revision_no"],
    } for r in rows]
    replay_total_eligible = sum(int(r["replay_eligible"] or 0)
                                for r in rows)
    replay_total_exact = sum(int(r["replay_exact"] or 0) for r in rows)
    replay_critical = sum(int(r["critical_replay_mismatch"] or 0)
                          for r in rows)
    certified = sum(int(r["certified_count"] or 0) for r in rows)
    no_trade = sum(int(r["no_trade_count"] or 0) for r in rows)
    abstain = sum(int(r["abstain_count"] or 0) for r in rows)
    safe_mode = sum(int(r["safe_mode_count"] or 0) for r in rows)
    halted = sum(int(r["halted_count"] or 0) for r in rows)
    total = certified + no_trade + abstain + safe_mode + halted

    def _pct(x):
        return round(100.0 * x / total, 2) if total else 0.0

    return {
        "release_id": release_id,
        "execution_mode": execution_mode,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "qualification": {
            "state": gate["state"],
            "qualified_days": gate["qualified_days"],
            "required_days": gate["required_days"],
            "remaining_days": gate["remaining_days"],
            "hard_reset_count": gate["hard_reset_count"],
            "blocking_reasons": gate["blocking_reasons"],
            "evidence_window_hash": gate["evidence_window_hash"],
        },
        "decision_support_qualification": {
            "state": ds_gate["state"],
            "shadow_state": ds_gate["shadow_state"],
            "outcome_days": ds_gate["outcome_days"],
            "required_outcome_days": ds_gate["required_outcome_days"],
            "remaining_outcome_days": ds_gate["remaining_outcome_days"],
            "observation_60d": ds_gate["observation_60d"],
            "evidence_window_hash": ds_gate["evidence_window_hash"],
        },
        "rolling_summary": rolling,
        "replay_summary": {
            "qualified_days_with_replay": sum(
                1 for r in rows if int(r["replay_eligible"] or 0) > 0),
            "total_eligible": replay_total_eligible,
            "total_exact": replay_total_exact,
            "critical_replay_mismatch": replay_critical,
            "eligible_rate": round(
                replay_total_exact / replay_total_eligible, 4)
            if replay_total_eligible else 0.0,
            "exact_rate": round(
                replay_total_exact / replay_total_eligible, 4)
            if replay_total_eligible else 0.0,
        },
        "terminal_state_distribution": {
            "certified": certified, "no_trade": no_trade,
            "abstain": abstain, "safe_mode": safe_mode,
            "halted": halted, "total": total,
            "certified_pct": _pct(certified),
            "no_trade_pct": _pct(no_trade),
            "abstain_pct": _pct(abstain),
            "safe_mode_pct": _pct(safe_mode),
            "halted_pct": _pct(halted),
            "note": "ABSTAIN/SAFE_MODE/HALTED 占比用于 Research/"
                    "Operational Review，不改变 Hard Gate",
        },
        "evidence_window": window,
        "rule": "任一阶段 NOT_PROVEN 不能被下游 PASS 抵消；"
                "20 日窗口内 Release 冻结",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="QCFP-MTF Runtime Closure Report（C2/C3 产物）")
    parser.add_argument("--release", default="MTR-CLOSURE-1")
    parser.add_argument("--mode", default="SHADOW",
                        choices=("SHADOW", "PAPER", "SMALL_LIVE"))
    parser.add_argument("--required-days", type=int, default=20)
    args = parser.parse_args(argv)
    conn = connect()
    try:
        report = build_closure_report(
            conn, args.release, args.mode,
            required_days=args.required_days)
    finally:
        conn.close()
    out_dir = get_report_root() / "audit" / "runtime_closure"
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(out_dir / "shadow_20d_qualification.json",
                report["qualification"])
    _write_json(out_dir / "shadow_20d_runtime_evidence.json",
                {"release_id": report["release_id"],
                 "execution_mode": report["execution_mode"],
                 "evidence_window": report["evidence_window"],
                 "rolling_summary": report["rolling_summary"]})
    _write_json(out_dir / "shadow_20d_replay_summary.json",
                report["replay_summary"])
    _write_json(out_dir / "shadow_terminal_state_distribution.json",
                report["terminal_state_distribution"])
    _write_json(out_dir / "runtime_closure_report.json", report)
    print(f"Closure Report: state={report['qualification']['state']} "
          f"qualified={report['qualification']['qualified_days']}/"
          f"{report['qualification']['required_days']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
