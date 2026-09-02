#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF 2.2 —— Stateful Shadow Mode（全历史重放，不改变交易）

对每只股票按 decision_date 顺序滚动运行唯一决策链
（Institutional → Exit Events → Setup → FSM → Sizing），
输出 prev_state / next_state / prev_position / target / permission_cap /
exit_event / decision_path / decision_id，并保存每个快照。
2.3 起同时写入决策台账 qcfp_decision_ledger（唯一决策事实源）：
不写交易、不覆盖 qcfp_mtf_decision，报告/审计只读 Ledger。

用法：python Core/QCFP_MTF/scripts/shadow_mode.py [--stock 00371]
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

import pandas as pd

from QCFP_MTF.common.db import connect
from QCFP_MTF.common.logger import setup_logger
from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.config.settings import load_qcfp_settings
from QCFP_MTF.decision.engine import evaluate
from QCFP_MTF.decision.decision_ledger import record_snapshot


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF 2.2 Stateful Shadow Mode")
    parser.add_argument("--stock", default=None)
    args = parser.parse_args(argv)
    settings = load_qcfp_settings()
    logger = setup_logger("shadow_mode", log_file="shadow_mode.log", mode="a")
    logger.info("=== Stateful Shadow Mode（2.2 全历史重放）启动 ===")

    conn = connect()
    try:
        d = pd.read_sql_query(
            """SELECT d.stock_code, d.stock_name, d.decision_date, d.mtf_regime,
                      d.structural_regime, d.monthly_behavior_state, d.tactical_signal,
                      d.risk_level, d.des_score, d.action_signal, d.base_action,
                      d.final_target, d.alignment_override, d.risk_override_active,
                      d.structure_behavior_alignment, d.data_quality,
                      d.chip_stability_confidence, d.market_context,
                      dt.daily_state,
                      s.c_state, s.f_state, s.p_state, s.q_position_52w,
                      s.available_date AS structural_available_date,
                      s.period_end AS q_period_end,
                      sp.f_state AS prev_f_state
               FROM qcfp_mtf_decision d
               LEFT JOIN qcfp_daily_tactical dt
                 ON dt.stock_code = d.stock_code
                AND dt.trade_date = (SELECT MAX(dt2.trade_date)
                                     FROM qcfp_daily_tactical dt2
                                     WHERE dt2.stock_code = d.stock_code
                                       AND dt2.trade_date <= d.decision_date)
               LEFT JOIN qcfp_quarterly_structural s
                 ON s.stock_code = d.stock_code
                AND s.period_end = (SELECT MAX(s2.period_end)
                                    FROM qcfp_quarterly_structural s2
                                    WHERE s2.stock_code = d.stock_code
                                      AND s2.available_date <= d.decision_date)
               LEFT JOIN qcfp_quarterly_structural sp
                 ON sp.stock_code = d.stock_code
                AND sp.period_end = (SELECT MAX(sp2.period_end)
                                     FROM qcfp_quarterly_structural sp2
                                     WHERE sp2.stock_code = d.stock_code
                                       AND sp2.period_end < s.period_end)
               ORDER BY d.stock_code, d.decision_date""", conn)
    finally:
        conn.close()
    if args.stock:
        d = d[d["stock_code"] == args.stock]
    if d.empty:
        logger.error("无决策数据")
        return 1

    stamp = datetime.now().strftime("%Y%m%d")
    run_id = f"shadow_{stamp}_{datetime.now():%H%M%S}"
    snapshots, snap_objs = [], []
    prev_state, prev_pos = {}, {}
    for _, r in d.iterrows():
        code = r["stock_code"]
        prev_fsm = prev_state.get(code, "FLAT")
        prev_p = prev_pos.get(code, 0.0)
        snap = evaluate(dict(r), prev_fsm, prev_p, settings, run_id=run_id)
        prev_state[code], prev_pos[code] = snap.next_fsm_state, snap.target_position
        snap_objs.append(snap)
        snapshots.append(snap.as_dict())
    out = pd.DataFrame(snapshots)
    latest = out.sort_values("decision_date").groupby("stock_code").tail(1)
    n_diff = int((latest["next_fsm_state"] != latest["prev_fsm_state"]).sum())
    logger.info(f"共 {len(out)} 个决策快照（{out['stock_code'].nunique()} 只），"
                f"最新截面状态变化 {n_diff} 只")
    for _, r in latest.iterrows():
        logger.info(
            f"  {r['stock_code']} {r['decision_date']}: Legacy {r.get('legacy_action', '—')} "
            f"→ New {r['institutional_permission']}+{r['setup_type']} "
            f"{r['prev_fsm_state']}→{r['next_fsm_state']} "
            f"target={r['target_position']} cap={r['permission_cap']} "
            f"exit={r['exit_event_kind']}")

    report_root = get_report_root() / "shadow"
    report_root.mkdir(parents=True, exist_ok=True)
    # 2.3：写入决策台账（正式事实源，报告只读 Ledger）
    conn = connect()
    try:
        for s in snap_objs:
            record_snapshot(conn, s, run_id, settings=settings)
    finally:
        conn.close()
    logger.info(f"决策台账已写入 {len(snapshots)} 条（run_id={run_id}）")
    (report_root / f"shadow_stateful_{stamp}.json").write_text(
        json.dumps({"generated_at": stamp, "rule_version": "2.2",
                    "schema_version": "1.0",
                    "run_id": run_id,
                    "input_contract": ["stock_code", "decision_date",
                                       "prev_fsm_state", "previous_position",
                                       "c_state", "f_state", "prev_f_state",
                                       "p_state", "risk_level", "des_score",
                                       "daily_state", "monthly_behavior_state",
                                       "tactical_signal", "settings_hash"],
                    "snapshots": snapshots}, ensure_ascii=False, indent=2,
                   default=str), encoding="utf-8")
    out.to_csv(report_root / f"shadow_stateful_{stamp}.csv",
               index=False, encoding="utf-8-sig")
    logger.info(f"Shadow 报告已保存: Report/QCFP_MTF/shadow/shadow_stateful_{stamp}.{{csv,json}}")
    logger.info("shadow_mode 完成 ✅（未写库、未改交易）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
