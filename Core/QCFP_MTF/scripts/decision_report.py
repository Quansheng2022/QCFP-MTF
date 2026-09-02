#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF 2.5 —— Decision Report（决策报告，报告三拆分之一）

回答"今天为什么允许/不允许交易"：一屏给出
    Institutional State → Permission → Participation → Setup → TQS
    → Risk → FSM → Final Target + Governance 核验 + 散户卡 + 二维矩阵

用法：python Core/QCFP_MTF/scripts/decision_report.py --stock 01951
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.config.settings import load_qcfp_settings
from QCFP_MTF.decision.decision_snapshot import load_canonical_decision
from QCFP_MTF.decision.retail import retail_card_lines


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF Decision Report")
    parser.add_argument("--stock", required=True)
    parser.add_argument("--date", default=None)
    args = parser.parse_args(argv)
    settings = load_qcfp_settings()

    from QCFP_MTF.common.db import connect
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
    try:
        snap, source = load_canonical_decision(row, settings)
    except Exception as exc:
        print(f"❌ 无正式决策：{exc}")
        return 1
    card = "\n".join(retail_card_lines(row, settings))
    from QCFP_MTF.explainability.graph import build_explainability_graph, \
        graph_to_md
    explain_md = graph_to_md(build_explainability_graph(snap))
    action_map = {"OBSERVATION": "OBSERVE", "RISK_BEARING": "TRADE",
                  "NONE": "STAND"}
    first_screen = [
        f"# QCFP-MTF Decision Report　{args.stock}　{date}\n",
        "```text",
        f"{args.stock}　{date}",
        "",
        f"Institutional　{snap.institutional_state}",
        f"Permission　{snap.institutional_permission}",
        f"Swing Setup　{snap.setup_type or 'NONE'}",
        f"Risk　{row.get('risk_level') or '—'}",
        f"FSM　{snap.prev_fsm_state} → {snap.next_fsm_state}",
        f"Previous Position　{snap.previous_position * 100:.0f}%",
        f"Raw Target　{snap.raw_target_position * 100:.0f}%",
        f"Final Target　{snap.target_position * 100:.0f}%",
        f"ACTION　{action_map.get(snap.position_class, snap.position_class)}",
        "Why?",
    ]
    first_screen += [f"{i}. {c}" for i, c in enumerate(
        (snap.primary_reason,) + tuple(snap.secondary_reasons), 1)]
    first_screen.append("```\n")
    lines = first_screen + [
             f"> 数据源：{source}\n",
             "> Structural Regime ≠ Institutional Permission ≠ Retail Swing Action\n",
             "### 牛散交易四问\n",
             "| 问 | 答 |", "| :-- | :-- |",
             f"| ① 能不能做？ | {snap.institutional_permission}"
             f"（上限 {snap.permission_cap}） |",
             f"| ② 为什么现在做？ | Setup {snap.setup_type or 'NONE'}　"
             f"TQS {snap.trade_quality:.0f}（{snap.trade_quality_band}） |",
             f"| ③ 最多做多少？ | {snap.participation_mode} ≤ "
             f"{snap.participation_cap * 100:.0f}%"
             f"（Raw {snap.raw_target_position * 100:.0f}% → "
             f"Final {snap.target_position * 100:.0f}%） |",
             f"| ④ 错了怎么办？ | FSM {snap.next_fsm_state}｜退出等级 "
             f"L{snap.exit_severity}｜原因 {snap.primary_reason} |\n",
             "## Governance Decision Card\n",
             "| 项 | 值 |", "| :-- | :-- |",
             f"| Institutional State | {snap.institutional_state} |",
             f"| Permission | **{snap.institutional_permission}**"
             f"（上限 {snap.permission_cap}） |",
             f"| Participation | **{snap.participation_mode} ≤ "
             f"{snap.participation_cap * 100:.0f}%** |",
             f"| Swing Setup | {snap.setup_type or '—'} |",
             f"| Trade Quality | **{snap.trade_quality:.0f} / 100"
             f"（{snap.trade_quality_band or '—'}）** |",
             f"| Risk | {row.get('risk_level') or '—'}"
             f"（DES={row.get('des_score') or 0}） |",
             f"| FSM | {snap.prev_fsm_state} → {snap.next_fsm_state} |",
             f"| Final Target | **{snap.target_position * 100:.0f}%** |",
             f"| 决策原因 | **{snap.primary_reason}**"
             f"（{','.join(snap.secondary_reasons) or '无'}） |",
             f"| 退出等级 | L{snap.exit_severity} |\n",
             "## Decision Explainability Graph\n",
             explain_md, "\n",
             card, "\n"]
    out_dir = get_report_root() / "decision"
    out_dir.mkdir(parents=True, exist_ok=True)
    md = "\n".join(lines)
    (out_dir / f"{args.stock}_decision_{date}.md").write_text(
        md, encoding="utf-8")
    (out_dir / f"{args.stock}_decision_{date}.json").write_text(
        json.dumps(snap.as_dict(), ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")
    print(f"Decision Report 已生成: {out_dir / f'{args.stock}_decision_{date}.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
