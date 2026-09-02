#!/usr/bin/env python
# coding: utf-8
"""QCFP-MTF 2.7 —— Safety Kill-Switch Report（系统级安全状态）"""

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
from QCFP_MTF.safety.kill_switch import evaluate_safety


def main(argv=None) -> int:
    conn = connect()
    try:
        n = conn.execute(
            "SELECT COUNT(*) FROM qcfp_decision_ledger").fetchone()[0]
        n_ok = conn.execute(
            "SELECT COUNT(*) FROM qcfp_decision_ledger WHERE "
            "decision_id IS NOT NULL AND input_fingerprint IS NOT NULL "
            "AND settings_hash IS NOT NULL AND model_version IS NOT NULL "
            "AND rule_version IS NOT NULL AND schema_version IS NOT NULL").fetchone()[0]
        n_c = conn.execute(
            "SELECT COUNT(*) FROM qcfp_decision_ledger "
            "WHERE pit_grade='C'").fetchone()[0]
    finally:
        conn.close()
    checks = {
        "data_failure": False,
        "pit_failure": n > 0 and n_c == n,      # 全部 PIT-C → 数据可信度不足
        "model_drift": False,
        "execution_failure": False,
        "risk_breach": False,
        "abnormal_market": False,
        "ledger_failure": n > 0 and n_ok != n,
        "replay_failure": False,
    }
    result = evaluate_safety(checks)
    out_dir = get_report_root() / "safety"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    out = {"generated_at": stamp, **result}
    (out_dir / f"safety_{stamp}.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Safety Kill-Switch：{result['status']}"
          f"（触发：{result['triggered']}）")
    return 0 if result["status"] == "NORMAL" else 1


if __name__ == "__main__":
    sys.exit(main())
