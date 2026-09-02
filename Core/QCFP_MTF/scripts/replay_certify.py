#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF 2.8 —— Replay Certification（回放证书）

校验 Live == Replay == Backtest == Ledger 指纹链：
    input_hash → decision_hash → certificate_hash → ledger_hash
任何不一致 → REPLAY_MISMATCH。

用法：
    python Core/QCFP_MTF/scripts/replay_certify.py --stock 01951
        [--date 2026-08-21] [--run-id bt_20260824_2]
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
from QCFP_MTF.config.settings import load_qcfp_settings
from QCFP_MTF.decision.decision_certificate import build_certificate
from QCFP_MTF.decision.decision_ledger import LEDGER_COLUMNS
from QCFP_MTF.decision.decision_snapshot import load_canonical_decision
from QCFP_MTF.decision.engine import evaluate
from QCFP_MTF.decision.replay_cert import certify_replay, ledger_fingerprint


def _load_ledger_row(conn, stock, date, run_id=""):
    sql = ("SELECT * FROM qcfp_decision_ledger "
           "WHERE stock_code=? AND decision_date=? AND status='ACTIVE'")
    args = [stock, date]
    if run_id:
        sql += " AND run_id=?"
        args.append(run_id)
    sql += " ORDER BY created_at DESC LIMIT 1"
    r = conn.execute(sql, args).fetchone()
    return dict(r) if r else None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF 回放证书")
    parser.add_argument("--stock", required=True)
    parser.add_argument("--date", default=None)
    parser.add_argument("--run-id", default="")
    args = parser.parse_args(argv)
    logger = setup_logger("replay_certify", log_file="replay_certify.log",
                          mode="a")
    settings = load_qcfp_settings()

    from QCFP_MTF.scripts.dss_report import _latest_decision, _row
    conn = connect()
    try:
        date = args.date or _latest_decision(conn, args.stock)
        row = _row(conn, args.stock, date) if date else None
        ledger = _load_ledger_row(conn, args.stock, date, args.run_id)
    finally:
        conn.close()
    if not row:
        print(f"❌ {args.stock} 无决策数据")
        return 1

    live_snap, source = load_canonical_decision(row, settings)
    if ledger:
        from QCFP_MTF.decision.decision_ledger import _snap_from_ledger_row
        from QCFP_MTF.decision.decision_snapshot import _snapshot_from_dict
        ledger_snap = _snapshot_from_dict(_snap_from_ledger_row(ledger))
        if ledger_snap is not None:
            live_snap = ledger_snap
            source = f"ledger:{ledger.get('run_id') or '?'}（正式事实源）"
    # 回放播种：优先用 Ledger 真实前序状态（否则 NON_CANONICAL 的 FLAT/0
    # 无法复现历史决策，认证必然失败——这是设计使然，不是 bug）。
    if ledger:
        replay_prev = ledger.get("previous_fsm_state") \
            or live_snap.prev_fsm_state
        replay_pos = float(ledger.get("previous_position")
                           if ledger.get("previous_position") is not None
                           else live_snap.previous_position)
        logger.info(f"回放播种自 Ledger：{replay_prev}@{replay_pos}")
    else:
        replay_prev, replay_pos = live_snap.prev_fsm_state, \
            live_snap.previous_position
    replay_snap = evaluate(
        row, replay_prev, replay_pos, settings, run_id=args.run_id)
    # 证书代表"被认证的决策"：以重放结果为准（Live 若为 NON_CANONICAL
    # 推算，其 FSM 起点并非历史事实，不能作为证书基底）。
    certificate = build_certificate(replay_snap)
    ledger_fp = ledger_fingerprint(ledger) if ledger else ""
    input_fields = ("stock_code", "decision_date", "c_state", "f_state",
                    "p_state", "prev_f_state", "tactical_signal",
                    "daily_state", "monthly_behavior_state", "risk_level",
                    "des_score", "stop_triggered", "chase_filter",
                    "chip_stability_confidence", "data_quality",
                    "structure_behavior_alignment", "q_position_52w",
                    "cooldown_remaining")
    cert = certify_replay(
        decision_id=live_snap.decision_id,
        input_snapshot=live_snap,
        replay_snapshot=replay_snap,
        backtest_snapshot=None,
        ledger_row=ledger,
        certificate=certificate,
        input_fields=input_fields)
    cert_dict = cert.as_dict()
    cert_dict["ledger_present"] = bool(ledger)
    cert_dict["source"] = source
    cert_dict["decision_date"] = date
    cert_dict["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if ledger:
        cert_dict["ledger_fingerprint"] = ledger_fp
        cert_dict["ledger_final_target"] = ledger.get("final_target")
        cert_dict["ledger_run_id"] = ledger.get("run_id")
        cert_dict["drift"] = {
            "input_fingerprint": {
                "ledger": ledger.get("input_fingerprint"),
                "replay": replay_snap.input_fingerprint,
                "drifted": bool(ledger.get("input_fingerprint")
                                and replay_snap.input_fingerprint
                                and ledger.get("input_fingerprint")
                                != replay_snap.input_fingerprint),
            },
            "settings_hash": {
                "ledger": ledger.get("settings_hash"),
                "replay": replay_snap.settings_hash,
                "drifted": bool(ledger.get("settings_hash")
                                and replay_snap.settings_hash
                                and ledger.get("settings_hash")
                                != replay_snap.settings_hash),
            },
        }

    report_root = get_report_root() / "replay_cert"
    report_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    json_path = report_root / f"replay_cert_{args.stock}_{stamp}.json"
    json_path.write_text(json.dumps(cert_dict, ensure_ascii=False, indent=2,
                                    default=str), encoding="utf-8")
    md = _to_md(cert_dict)
    md_path = report_root / f"replay_cert_{args.stock}_{stamp}.md"
    md_path.write_text(md, encoding="utf-8")
    print(md)
    logger.info(f"ReplayCert {cert.status} | {args.stock} {date} | "
                f"{cert.chain}")
    return 0 if cert.status == "VERIFIED" else 2


def _to_md(o: dict) -> str:
    status = o["status"]
    lines = [
        f"# Replay Certification　{o.get('decision_id', '')}",
        "",
        f"**状态：{'✅ VERIFIED' if status == 'VERIFIED' else '❌ REPLAY_MISMATCH'}**",
        "",
        f"- 股票：{o.get('decision_id', '').split('_')[0] if o.get('decision_id') else ''}　"
        f"决策日：{o['decision_date']}",
        f"- 数据源：{o.get('source', '')}",
        f"- Ledger：{'存在' if o.get('ledger_present') else '缺失'}",
        "",
        "## 指纹链",
        "",
        "```text",
    ]
    lines += [f"{c}" for c in o["chain"]]
    lines += ["```", ""]
    if o.get("reasons"):
        lines += ["## 不一致明细", ""]
        lines += [f"- {r}" for r in o["reasons"]]
        lines += [""]
    if o.get("diffs"):
        lines += ["## Diff", ""]
        lines += [f"- {d}" for d in o["diffs"]]
        lines += [""]
    if o.get("drift"):
        lines += ["## 输入/设置漂移诊断（不影响决策指纹）", ""]
        for key, info in o["drift"].items():
            mark = "⚠️ 漂移" if info.get("drifted") else "✅ 一致"
            lines.append(
                f"- {key}：{mark}（ledger=`{info.get('ledger')}` / "
                f"replay=`{info.get('replay')}`）")
        lines += [""]
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
