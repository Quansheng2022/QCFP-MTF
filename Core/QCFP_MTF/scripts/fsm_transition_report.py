#!/usr/bin/env python
# coding: utf-8
"""QCFP-MTF 2.7 —— FSM State Transition Report（状态转移概率矩阵）"""

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
from QCFP_MTF.fsm.transition_matrix import (expected_state_value,
                                            transition_matrix_by)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="FSM Transition Report")
    p.add_argument("--stock", default=None)
    args = p.parse_args(argv)
    conn = connect()
    try:
        sql = ("SELECT stock_code, decision_date, previous_fsm_state, "
               "next_fsm_state, institutional_permission "
               "FROM qcfp_decision_ledger WHERE status='ACTIVE'")
        params = []
        if args.stock:
            sql += " AND stock_code=?"
            params.append(args.stock)
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    import pandas as pd
    df = pd.DataFrame([dict(r) for r in rows])
    if df.empty:
        print("❌ 台账为空（先运行 shadow_mode）")
        return 1
    overall = transition_matrix_by(df, by_cols=("stock_code",))
    # 全市场整体矩阵：把每只股票的 next 序列拼接
    seq = df.sort_values(["stock_code", "decision_date"])[
        "next_fsm_state"].tolist()
    from QCFP_MTF.fsm.transition_matrix import build_transition_matrix
    overall_matrix = build_transition_matrix(seq)
    by_permission = transition_matrix_by(df, by_cols=("institutional_permission",))
    state_values = {"TESTING": 0.2, "BUILDING": 0.5, "HOLDING": 1.0,
                    "TRIMMING": 0.3, "EXITING": -0.2, "COOLDOWN": 0.0,
                    "FLAT": 0.0}
    ev = expected_state_value(overall_matrix, state_values)
    out_dir = get_report_root() / "fsm_transition"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    focus = args.stock or "all"
    out = {"generated_at": stamp, "focus": focus,
           "overall_matrix": overall_matrix,
           "expected_state_value": ev,
           "by_permission": by_permission}
    (out_dir / f"fsm_transition_{focus}_{stamp}.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"FSM Transition Report 已保存: {focus}_{stamp}.json")
    print("期望状态价值：", ev)
    return 0


if __name__ == "__main__":
    sys.exit(main())
