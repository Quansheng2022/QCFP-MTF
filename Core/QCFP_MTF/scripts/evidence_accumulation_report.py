#!/usr/bin/env python
# coding: utf-8
"""Evidence Accumulation Health Report（P0-6）

每天只回答 6 个问题：
    1. 今天证据完整吗？
    2. 当前连续合格几天？
    3. 为什么还没有 Qualified？
    4. 哪些 Outcome 已成熟？
    5. 是否发生任何 hard reset？
    6. 距离 DECISION_SUPPORT_QUALIFIED 还差什么？

输出：Report/QCFP_MTF/audit/runtime_evidence/evidence_accumulation_report.json
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
from QCFP_MTF.governance.evidence_freeze_contract import load_freeze_contract
from QCFP_MTF.governance.runtime_promotion_gate import \
    evaluate_decision_support_qualification
from QCFP_MTF.monitoring.replay_accumulation import \
    evaluate_replay_accumulation
from QCFP_MTF.monitoring.runtime_evidence_store import (
    load_runtime_evidence_window, outcome_qualified_days,
    rolling_evidence_summary, rolling_windows_summary)


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2,
                               default=str), encoding="utf-8")


def build_accumulation_report(conn, release_id, execution_mode="SHADOW",
                              required_days=20) -> dict:
    rows = load_runtime_evidence_window(
        conn, release_id, execution_mode, "2000-01-01", "2999-12-31")
    freeze = load_freeze_contract()
    shadow = evaluate_decision_support_qualification(
        rows, shadow_days=required_days, outcome_days=required_days)
    replay = evaluate_replay_accumulation(rows)
    windows = rolling_windows_summary(rows, required_days=required_days)
    outcome = outcome_qualified_days(rows)
    latest = rows[-1] if rows else {}
    daily_state = latest.get("daily_evidence_state") or "NO_DAILY_EVIDENCE"
    hard_reset_count = shadow.get("hard_reset_count", 0) \
        if "hard_reset_count" in shadow else \
        sum(1 for r in rows if int(r.get("invalidated") or 0) == 1)
    shadow_required = shadow.get("shadow_days") or shadow.get(
        "required_days") or 20
    shadow_remaining = shadow.get("remaining_days",
                                  max(0, shadow_required
                                      - shadow.get("qualified_days", 0)))
    return {
        "release_id": release_id,
        "evidence_freeze_id": freeze.get("evidence_freeze_id", ""),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "answers": {
            "1_daily_evidence_complete": {
                "daily_evidence_state": daily_state,
                "latest_trade_date": latest.get("trade_date"),
                "latest_verdict": latest.get("verdict"),
            },
            "2_consecutive_qualified_days": {
                "qualified_days": shadow["qualified_days"],
                "required_days": shadow_required,
                "remaining_days": shadow_remaining,
            },
            "3_why_not_qualified": {
                "state": shadow["state"],
                "blocking_reasons": (shadow.get("blocking_reasons")
                                     or [])[:10],
            },
            "4_outcome_matured": {
                "outcome_qualified_days": outcome["outcome_qualified_days"],
                "required_outcome_days": outcome["required_days"],
                "remaining_outcome_days": outcome["remaining_days"],
                "latest_outcome": {
                    "maturity_5d": latest.get("outcome_maturity_5d"),
                    "maturity_20d": latest.get("outcome_maturity_20d"),
                    "maturity_60d": latest.get("outcome_maturity_60d"),
                    "coverage": latest.get("outcome_coverage"),
                },
            },
            "5_hard_reset": {
                "hard_reset_count": hard_reset_count,
                "invalidated_days": sum(
                    1 for r in rows if int(r.get("invalidated") or 0) == 1),
            },
            "6_distance_to_qualified": {
                "state": shadow["state"],
                "remaining_shadow_days": shadow_remaining,
                "remaining_outcome_days":
                    shadow["remaining_outcome_days"],
                "replay": {"state": replay["state"],
                           "window_exact_rate":
                               replay["stats"]["window_exact_rate"],
                           "replay_gap_days":
                               replay["stats"]["replay_gap_days"]},
            },
        },
        "shadow": {"state": shadow["state"],
                   "qualified_days": shadow["qualified_days"],
                   "required_days": shadow_required,
                   "remaining_days": shadow_remaining},
        "replay": replay,
        "outcome": outcome,
        "windows": {"5d": windows["5d"]["qualified_days"],
                    "20d": windows["20d"]["qualified_days"],
                    "60d": windows["60d"]["qualified_days"],
                    "120d": windows["120d"]["qualified_days"]},
        "observation_60d": shadow["observation_60d"],
        "rule": "健康报告只读 Verified Evidence；"
                "20D blocking、60D observation、120D health",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="QCFP-MTF Evidence Accumulation Health Report")
    parser.add_argument("--release", default="MTR-CLOSURE-1")
    parser.add_argument("--mode", default="SHADOW")
    parser.add_argument("--required-days", type=int, default=20)
    args = parser.parse_args(argv)
    conn = connect()
    try:
        report = build_accumulation_report(
            conn, args.release, args.mode, required_days=args.required_days)
    finally:
        conn.close()
    out_dir = get_report_root() / "audit" / "runtime_evidence"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "evidence_accumulation_report.json"
    _write_json(path, report)
    a = report["answers"]
    print("Evidence Accumulation Status")
    print("----------------------------")
    print(f"Release: {report['release_id']}")
    print(f"Freeze ID: {report['evidence_freeze_id'] or 'NONE'}")
    print(f"Daily Evidence: {a['1_daily_evidence_complete']['daily_evidence_state']}")
    print(f"Shadow: {a['2_consecutive_qualified_days']['qualified_days']} / "
          f"{a['2_consecutive_qualified_days']['required_days']} qualified days")
    print(f"Replay: {report['replay']['stats']['window_replay_exact']} / "
          f"{report['replay']['stats']['window_replay_eligible']} exact, "
          f"gap={report['replay']['stats']['replay_gap_days']}")
    print(f"Outcome: 5D={a['4_outcome_matured']['latest_outcome']['maturity_5d']} "
          f"20D={a['4_outcome_matured']['latest_outcome']['maturity_20d']} "
          f"60D={a['4_outcome_matured']['latest_outcome']['maturity_60d']}")
    print(f"Current State: {report['shadow']['state']}")
    print(f"Blocking: {a['3_why_not_qualified']['blocking_reasons'] or 'None'}")
    print(f"60D Observation: {report['observation_60d']}")
    print(f"→ {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
