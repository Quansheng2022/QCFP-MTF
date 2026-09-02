#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF 2.8 —— Counterfactual Decision Replay（反事实决策回放）

同一次决策，逐模块关闭，回答"每个模块到底贡献了多少"：
    Actual（全开）  vs  Counterfactual（关 Permission / Wave / Risk /
    Portfolio / Daily / HardExit）

对比维度：target_position / next_fsm_state / primary_reason / action。

用法：
    python Core/QCFP_MTF/scripts/counterfactual_replay.py --stock 01951
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
from QCFP_MTF.decision.decision_snapshot import load_canonical_decision
from QCFP_MTF.decision.engine import DecisionConfig, evaluate
from QCFP_MTF.decision.object import build_unified_decision, \
    validate_unified_decision


VARIANT_SPECS = [
    ("full", "全模块开启（Actual）", None),
    ("no_permission", "关闭 Institutional Permission",
     {"use_permission": False}),
    ("no_wave", "关闭 Wave/Setup 信号", None),   # 特殊处理：中性化行
    ("no_risk", "关闭 Risk 约束", None),          # 特殊处理：risk_level=Low
    ("no_portfolio", "关闭 Portfolio 约束", None),  # 特殊处理：portfolio=NORMAL
    ("no_daily", "关闭日线战术层", {"use_daily": False}),
    ("no_hard_exit", "关闭 Hard Exit", {"use_hard_exit": False}),
]


def _variant_config(name, overrides) -> DecisionConfig:
    return DecisionConfig(**overrides) if overrides else DecisionConfig()


def _variant_row(name, row):
    """对特殊变体做输入中性化（不修改原 row）。"""
    r = dict(row)
    if name == "no_wave":
        r["tactical_signal"] = "Consolidation"
        r["daily_state"] = "DAILY_NEUTRAL"
        r["wave_strength"] = 0.0
    elif name == "no_risk":
        r["risk_level"] = "Low"
        r["des_score"] = 0
    elif name == "no_portfolio":
        r["portfolio_state"] = "NORMAL"
    return r


def replay_variant(row, previous_state, previous_position, settings,
                   name, overrides, run_id="") -> dict:
    """单变体重放：返回快照 + 关键指标。"""
    cfg = _variant_config(name, overrides)
    r = _variant_row(name, row)
    snap = evaluate(r, previous_state, previous_position, settings,
                    config=cfg, run_id=run_id)
    return {
        "variant": name,
        "config": {k: getattr(cfg, k) for k in
                   ("use_permission", "use_soft_exit", "use_hard_exit",
                    "use_daily", "use_budget", "use_market_scale",
                    "use_stop", "use_observation",
                    "use_data_quality_gate", "use_regime_params")},
        "target_position": snap.target_position,
        "previous_position": snap.previous_position,
        "next_fsm_state": snap.next_fsm_state,
        "primary_reason": snap.primary_reason,
        "secondary_reasons": list(snap.secondary_reasons),
        "action": snap.context.get("action") or "",
        "permission": snap.institutional_permission,
        "exit_event": snap.exit_event_kind,
        "input_fingerprint": snap.input_fingerprint,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF 反事实决策回放")
    parser.add_argument("--stock", required=True)
    parser.add_argument("--date", default=None)
    parser.add_argument("--run-id", default="counterfactual")
    args = parser.parse_args(argv)
    logger = setup_logger("counterfactual_replay",
                          log_file="counterfactual_replay.log", mode="a")
    settings = load_qcfp_settings()

    from QCFP_MTF.scripts.dss_report import _latest_decision, _row
    conn = connect()
    try:
        date = args.date or _latest_decision(conn, args.stock)
        row = _row(conn, args.stock, date) if date else None
    finally:
        conn.close()
    if not row:
        print(f"❌ {args.stock} 无决策数据")
        return 1

    snap, source = load_canonical_decision(row, settings)
    prev_state = snap.prev_fsm_state
    prev_pos = snap.previous_position
    logger.info(f"反事实回放 {args.stock} {date} 基准={prev_state}@{prev_pos}")

    results = []
    for name, label, overrides in VARIANT_SPECS:
        res = replay_variant(row, prev_state, prev_pos, settings,
                             name, overrides, run_id=args.run_id)
        res["label"] = label
        results.append(res)

    actual = results[0]
    deltas = []
    for res in results[1:]:
        delta = {
            "variant": res["variant"],
            "target_delta": round(
                res["target_position"] - actual["target_position"], 4),
            "fsm_changed": res["next_fsm_state"] != actual["next_fsm_state"],
            "reason_changed": res["primary_reason"] != actual["primary_reason"],
            "action_changed": res["action"] != actual["action"],
        }
        deltas.append(delta)

    # 11 号：统一决策对象（full 变体）
    unified = build_unified_decision(snap, mode="REPLAY")
    violations = validate_unified_decision(unified)
    output = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stock": args.stock, "decision_date": date,
        "source": source, "run_id": args.run_id,
        "baseline": {"prev_fsm_state": prev_state,
                     "previous_position": prev_pos},
        "results": results,
        "deltas": deltas,
        "unified_decision": {
            "decision_id": unified.decision_id,
            "version_hash": unified.version_hash,
            "decision_hash": unified.decision_hash,
            "consumers": list(unified.consumers),
            "violations": violations,
        },
    }
    report_root = get_report_root() / "counterfactual"
    report_root.mkdir(parents=True, exist_ok=True)
    json_path = report_root / \
        f"counterfactual_{args.stock}_{datetime.now().strftime('%Y%m%d')}.json"
    json_path.write_text(json.dumps(output, ensure_ascii=False, indent=2,
                                    default=str), encoding="utf-8")

    md = _to_md(output)
    md_path = report_root / \
        f"counterfactual_{args.stock}_{datetime.now().strftime('%Y%m%d')}.md"
    md_path.write_text(md, encoding="utf-8")
    print(md)
    logger.info(f"已输出 {json_path} / {md_path}")
    return 0


def _to_md(o: dict) -> str:
    lines = [
        f"# Counterfactual Decision Replay　{o['stock']}　{o['decision_date']}",
        "",
        f"> 数据源：{o['source']}　|　run_id：{o['run_id']}",
        f"> 基线：{o['baseline']['prev_fsm_state']} @ "
        f"{o['baseline']['previous_position']:.0%}",
        "",
        "| 变体 | 目标仓位 | FSM | 主因 | Action | 相对 Actual Δ仓位 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    actual = o["results"][0]
    for res in o["results"]:
        delta = next((d["target_delta"] for d in o["deltas"]
                      if d["variant"] == res["variant"]), 0.0)
        lines.append(
            f"| {res['label']} | {res['target_position']:.1%} | "
            f"{res['next_fsm_state']} | {res['primary_reason']} | "
            f"{res['action']} | {delta:+.1%} |")
    lines += [
        "",
        "## Unified Decision Object（11 号）",
        "",
        f"- decision_id：`{o['unified_decision']['decision_id']}`",
        f"- version_hash：`{o['unified_decision']['version_hash']}`",
        f"- decision_hash：`{o['unified_decision']['decision_hash']}`",
        f"- consumers：{', '.join(o['unified_decision']['consumers'])}",
        f"- 一致性违规："
        f"{'无' if not o['unified_decision']['violations'] else o['unified_decision']['violations']}",
        "",
        "## 结论",
        "",
    ]
    changed = [d for d in o["deltas"]
               if abs(d["target_delta"]) > 1e-9 or d["fsm_changed"]]
    lines.append(
        f"模块关闭导致 {len(changed)}/{len(o['deltas'])} 个变体改变决策："
        + ("；".join(d["variant"] for d in changed) if changed else "无"))
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
