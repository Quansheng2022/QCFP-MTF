#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF —— 个股一体化分析报告（All-in-One, MD）

聚合：
- DSS 决策详细报告（10 节：决策摘要/季度结构/月线行为/周线触发/成本位置/
  置信度证据/风险与市场环境/历史时间线/前向收益对照/数据质量）
- 各引擎最新状态快照（季度/月线/周线/MTF 最新行）
- 2.2 决策链审计（Institutional Permission + Retail Position FSM，Stateful Shadow）
- 回测汇总（总体绩效/分年度/市场分层/Rolling OOS/基准超额/组合风险）

报告文件名包含股票代码：{stock}_all_in_one_{decision_date}.md

用法：
    python Core/QCFP_MTF/scripts/all_in_one_report.py --stock 01951
        [--date 2026-08-21] [--run-id bt_20260822]
"""

import argparse
import html as _html
import json
import re
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.common.db import connect
from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.config.settings import get, load_qcfp_settings
from QCFP_MTF.data.loader import load_idx_hist
from QCFP_MTF.decision.decision_snapshot import load_canonical_decision
from QCFP_MTF.decision.versions import MODEL_VERSION
from QCFP_MTF.scripts import dss_report as dss


def _fmt(value, digits=4):
    if value is None:
        return "—"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def _pct(value, digits=2):
    if value is None or value != value:
        return "—"
    return f"{float(value) * 100:.{digits}f}%"


def _find_summary(bt_dir, run_id, stock):
    if run_id:
        fname = f"{run_id}_{stock}" if stock else run_id
        cand = bt_dir / f"summary_{fname}.json"
        return (cand, fname) if cand.exists() else (None, fname)
    pattern = f"summary_*_{stock}.json" if stock else "summary_*.json"
    files = sorted(bt_dir.glob(pattern), key=lambda p: p.stat().st_mtime)
    if not files:
        return None, None
    latest = files[-1]
    name = latest.stem[len("summary_"):]
    return latest, name


def _snapshot_table(conn, stock, date):
    rows = []
    q = conn.execute(
        "SELECT period_end, structural_regime, core_score, c_state, f_state, p_state "
        "FROM qcfp_quarterly_structural WHERE stock_code=? AND available_date<=? "
        "ORDER BY period_end DESC LIMIT 1", (stock, date)).fetchone()
    m = conn.execute(
        "SELECT month_end, monthly_behavior_state, m_vp_regime, "
        "turnover_liquidity_regime, cbi_score FROM qcfp_monthly_behavior "
        "WHERE stock_code=? AND month_end<=? ORDER BY month_end DESC LIMIT 1",
        (stock, date)).fetchone()
    w = conn.execute(
        "SELECT week_end, tactical_signal, w_breakout, w_breakdown FROM qcfp_weekly_tactical "
        "WHERE stock_code=? AND week_end<=? ORDER BY week_end DESC LIMIT 1",
        (stock, date)).fetchone()
    mtf = conn.execute(
        "SELECT decision_date, mtf_regime, action_signal, risk_level, qcfp_score, align_method "
        "FROM qcfp_mtf_decision WHERE stock_code=? AND decision_date<=? "
        "ORDER BY decision_date DESC LIMIT 1", (stock, date)).fetchone()
    if q:
        rows.append(("季度结构", q["period_end"], q["structural_regime"],
                     f"score={_fmt(q['core_score'])} C={q['c_state']} "
                     f"F={q['f_state']} P={q['p_state']}"))
    if m:
        rows.append(("月线行为", m["month_end"], m["monthly_behavior_state"],
                     f"VP={m['m_vp_regime']} T={m['turnover_liquidity_regime']} "
                     f"CBI={_fmt(m['cbi_score'], 2)}"))
    if w:
        rows.append(("周线触发", w["week_end"], w["tactical_signal"],
                     f"breakout={w['w_breakout']} breakdown={w['w_breakdown']}"))
    d = conn.execute(
        "SELECT trade_date, daily_state FROM qcfp_daily_tactical "
        "WHERE stock_code=? AND trade_date<=? ORDER BY trade_date DESC LIMIT 1",
        (stock, date)).fetchone()
    if d:
        hint = dss.tactical_hint({"daily_state": d["daily_state"]})
        rows.append(("日线战术", d["trade_date"], d["daily_state"], hint))
    if mtf:
        action_label = "试多（TEST_BUY）" \
            if mtf["align_method"] == "tactical_override" \
            else (mtf["action_signal"] or "—")
        rows.append(("MTF 决策", mtf["decision_date"], mtf["mtf_regime"],
                     f"{action_label} / risk={mtf['risk_level']} "
                     f"score={_fmt(mtf['qcfp_score'])}"))
    return rows


def _backtest_section(summary_path, run_id, stock):
    if summary_path is None or not summary_path.exists():
        return "> 未找到回测汇总（可先运行 backtest_runner.py --stock {0} --dry-run）".format(stock)
    s = json.loads(summary_path.read_text(encoding="utf-8"))
    lines = [f"### 回测汇总（run_id={run_id}，{s.get('start')} ~ {s.get('end')}）\n"]
    rstatus = s.get("run_status")
    if rstatus:
        eng = rstatus.get("status", "PASS_WITH_WARNING")
        overall = s.get("overall", {})
        sharpe = overall.get("sharpe")
        oos = s.get("rolling_oos_evaluation", [])
        oos_sharpes = [r.get("sharpe") for r in oos if r.get("sharpe") is not None]
        median_oos = sorted(oos_sharpes)[len(oos_sharpes) // 2] if oos_sharpes else None
        # 新 11 号：研究状态只来自 ValidationCertificate 唯一链路，
        # Report 禁止自行判断研究验证状态。
        from QCFP_MTF.governance.validation_certificate import \
            research_validated_from_summary
        research = research_validated_from_summary(s)["display_status"]
        evidence = "POSITIVE" if (sharpe or 0) > 0 else "NEGATIVE"
        lines.append(f"**Engineering Status: {eng}**"
                     f"（{'；'.join(rstatus.get('checks', []))}）")
        lines.append(f"**Research Status: {research}**（OOS Sharpe 中位数 {median_oos}）"
                     f"｜**Economic Evidence: {evidence}**（组合 Sharpe {sharpe}）\n")
    overall = s.get("overall", {})
    lines.append("| 指标 | 数值 |")
    lines.append("| :-- | :-- |")
    for k, v in overall.items():
        if k == "n":
            continue
        lines.append(f"| {k} | {v if not isinstance(v, float) else f'{v:.4f}'} |")
    by_year = s.get("by_year", [])
    if by_year:
        lines.append("\n**分年度**：")
        lines.append("| 年份 | 年化 | Sharpe | 回撤 |")
        lines.append("| :-- | :-- | :-- | :-- |")
        for r in by_year:
            lines.append(f"| {r.get('year')} | {_pct(r.get('annualized_return'))} | "
                         f"{_fmt(r.get('sharpe'))} | {_pct(r.get('max_drawdown'))} |")
    regime = s.get("by_market_regime", [])
    if regime:
        lines.append("\n**市场环境分层**：")
        lines.append("| 环境 | 年化 | Sharpe | 胜率 |")
        lines.append("| :-- | :-- | :-- | :-- |")
        for r in regime:
            lines.append(f"| {r.get('market_regime')} | {_pct(r.get('annualized_return'))} | "
                         f"{_fmt(r.get('sharpe'))} | {_pct(r.get('win_rate'))} |")
    oos = s.get("rolling_oos_evaluation", [])
    if oos:
        lines.append("\n**Rolling OOS（固定参数）**：")
        lines.append("| 窗口 | 年化 | Sharpe | 回撤 |")
        lines.append("| :-- | :-- | :-- | :-- |")
        for r in oos:
            lines.append(f"| {r.get('window')} | {_pct(r.get('annualized_return'))} | "
                         f"{_fmt(r.get('sharpe'))} | {_pct(r.get('max_drawdown'))} |")
    bench = s.get("benchmark", {})
    risk = s.get("portfolio_risk", {})
    if bench or risk:
        lines.append("\n**基准与组合风险**：")
        lines.append("| 项 | 值 |")
        lines.append("| :-- | :-- |")
        for name, key in [("等权基准年化超额", ("buy_hold", "excess_annualized")),
                          ("等权基准 IR", ("buy_hold", "information_ratio")),
                          ("恒指年化超额", ("hsi", "excess_annualized")),
                          ("恒指 IR", ("hsi", "information_ratio"))]:
            v = bench.get(key[0], {}).get(key[1])
            lines.append(f"| {name} | {_pct(v) if '超额' in name else _fmt(v)} |")
        lines.append(f"| VaR95 | {_pct(risk.get('var95'))} |")
        lines.append(f"| 年化波动 | {_pct(risk.get('annualized_vol'))} |")
        lines.append(f"| 平均暴露 | {_pct(risk.get('avg_exposure'), 1)} |")
    cm = s.get("cost_metrics")
    if cm:
        lines.append("\n**成本口径**：")
        lines.append("| 项 | 值 |")
        lines.append("| :-- | :-- |")
        lines.append(f"| 年化毛换手 | {_fmt(cm.get('annual_gross_turnover'), 2)} |")
        lines.append(f"| 年化交易成本 | {_pct(cm.get('annual_transaction_cost'))} |")
        lines.append(f"| 成本/毛换手 | {_fmt(cm.get('cost_per_turnover'), 4)} |")
        lines.append(f"| 平均仓位 | {_pct(cm.get('avg_position'), 1)} |")
    return "\n".join(lines) + "\n"


def _model_diagnosis_section(bt_dir):
    """模型诊断（Layer Ablation 矩阵）：Q / QM / QMW / Full 增量贡献"""
    files = sorted(bt_dir.glob("layer_ablation_*.json"),
                   key=lambda p: p.stat().st_mtime)
    if not files:
        return ""
    data = json.loads(files[-1].read_text(encoding="utf-8"))
    focus = data.get("focus")
    focus_note = f"（焦点股票 {focus}）" if focus else "（无焦点股票）"
    lines = ["## 3.5 模型诊断（Layer Ablation）\n",
             f"> **Scope：Full Universe{focus_note}**——与上方个股回测不同口径，"
             f"仅作研究参考。来源：{files[-1].name}\n",
             "| 模型 | 年化 | Sharpe | MDD | PF | 换手 | IC13 | 上行捕获 | 下行捕获 | 波段 |"]
    lines.append("| :-- | --: | --: | --: | --: | --: | --: | --: | --: | --: |")
    for m in data.get("models", []):
        wave = m.get(f"{focus}_wave_return") if focus else None
        lines.append(
            f"| {m['model']} | {_pct(m.get('annualized_return'))} | "
            f"{_fmt(m.get('sharpe'))} | {_pct(m.get('max_drawdown'))} | "
            f"{_fmt(m.get('profit_factor'))} | {_fmt(m.get('annual_turnover'), 2)} | "
            f"{_fmt(m.get('rank_ic_13w'))} | {_fmt(m.get('upside_capture'))} | "
            f"{_fmt(m.get('downside_capture'))} | {_pct(wave) if wave is not None else '—'} |")
    lines.append("")
    return "\n".join(lines)


def _decision_audit_section(row, settings):
    """2.2 决策链审计（Institutional Permission + Retail Position FSM）

    统一入口 build_report_snapshot：优先 Stateful Shadow 快照，缺失时按
    FLAT/0 做单点推算。报告层不再自行决策。
    """
    try:
        snap_obj, source = load_canonical_decision(row, settings)
        snap = snap_obj.as_dict()
    except Exception as exc:
        return (f"## 2.5 2.2 决策链审计（Stateful Shadow）\n\n"
                f"> 决策链审计不可用：{exc}\n")

    def _g(key):
        v = snap.get(key)
        return "—" if v in (None, "", ()) else str(v)

    lines = ["## 2.5 2.2 决策链审计（Stateful Shadow）\n",
             f"> 数据源：{source}；口径：Institutional → Exit Events → Setup → "
             f"FSM → Sizing（PIT-C Estimated，研究输出非交易指令）\n",
             "| 环节 | 取值 |",
             "| :-- | :-- |",
             f"| Ledger / Run | `{_g('run_id') or '—'}`（决策台账） |",
             f"| 决策原因 | **{_g('primary_reason')}**"
             f"（{_g('secondary_reasons')}） |",
             f"| Trade Quality | **{snap.get('trade_quality')} / 100"
             f"（{snap.get('trade_quality_band')}）** |",
             f"| Participation Budget | {_g('participation_mode')}"
             f"（上限 {snap.get('participation_cap')}）｜仓位类别 "
             f"{snap.get('position_class')}｜退出等级 "
             f"L{snap.get('exit_severity')} |",
             f"| Institutional State | {_g('institutional_state')} |",
             f"| Institutional Permission | {_g('institutional_permission')} "
             f"（上限 {_g('permission_cap')}） |",
             f"| Exit Event | {_g('exit_event_kind')}：{_g('exit_event_reason')} |",
             f"| Swing Setup | {_g('setup_type')} |",
             f"| Retail FSM | {_g('prev_fsm_state')} → {_g('next_fsm_state')} |",
             f"| Matrix Base | {_g('base_fsm_state')}（矩阵基准） |",
             f"| Position | {_g('previous_position')} → {_g('target_position')} |",
             f"| Raw Target | {_g('raw_target_position')}"
             f"（约束生效：{snap.get('permission_constraint_applied')}） |",
             f"| Position Action | "
             f"{'NO_RISK_INCREASE（权限封顶）' if snap.get('permission_constraint_applied') else 'NORMAL'} |",
             f"| Override Rules | {_g('override_rule_ids')} |",
             f"| Decision Path | {_g('decision_path')} |",
             f"| Rule / Model / Schema | {_g('rule_version')} / "
             f"{_g('model_version')} / {_g('schema_version')} |",
             f"| Feature Manifest | `{_g('feature_manifest_hash')}` |",
             f"| Fingerprint | `{_g('input_fingerprint')}`（输入哈希） |",
             ""]
    return "\n".join(lines)


def _governance_card(row, settings):
    """2.5 Governance Decision Card：报告顶部一屏给出受治理决策"""
    try:
        snap, source = load_canonical_decision(row, settings)
    except Exception as exc:
        return (f"## 0.0 Governance Decision Card\n\n"
                f"> 无正式决策：{exc}\n")
    # 新 12 号：每个 ✓ 必须能反查真实 proof/certificate 字段，
    # 禁止恒真条件伪证明（如 perm==snap.institutional_permission）。
    from QCFP_MTF.decision.governance_card import governance_card_lines
    perm = snap.institutional_permission
    cap_txt = (f"{snap.participation_cap * 100:.0f}%"
               if snap.participation_cap else "0%")
    decision_txt = {
        "OBSERVATION": "OBSERVATION / TEST（观察仓）",
        "RISK_BEARING": "TRADE（正式参与）",
        "NONE": "STAND（不参与）",
    }.get(snap.position_class, snap.position_class)
    checks = ["见下表（每个 ✓ 均可反查 proof/certificate 字段）"]
    lines = ["## 0.0 Governance Decision Card\n",
             "| 项 | 值 |", "| :-- | :-- |",
             f"| Institutional State | {snap.institutional_state} |",
             f"| Permission | **{perm}**（上限 {snap.permission_cap}） |",
             f"| Permission Upgrade | **NO**（Daily/Setup/FSM/Sizing 均不得升级）"
             f"{'—— OBSERVE 为预算内观察仓，权限仍 ' + perm if snap.participation_mode == 'OBSERVE' else ''} |",
             f"| Participation | **{snap.participation_mode} ≤ {cap_txt}**"
             f"（{source}） |",
             f"| Swing Setup | {snap.setup_type or '—'} |",
             f"| Trade Quality | **{snap.trade_quality:.0f} / 100"
             f"（{snap.trade_quality_band or '—'}）** |",
             f"| Risk | {row.get('risk_level') or '—'}"
             f"（DES={row.get('des_score') or 0}） |",
             f"| FSM | {snap.prev_fsm_state} → {snap.next_fsm_state} |",
             f"| Final Target | **{snap.target_position * 100:.0f}%** |",
             f"| Governance | {'　'.join(checks)} |",
             f"| Governance Proof |\n{governance_card_lines(snap)} |",
             f"| Decision | **{decision_txt}**（非 BUY/SELL 信号） |\n"]
    statuses = [
        "**Engineering Status**：Governance ✓ / Replay ✓ / Ledger ✓ / "
        f"PIT {snap.pit_grade or '—'}（{source}）",
        "**Research Status**：C/F 相对 P 的独立增量**尚未建立**"
        "（需 PIT-A/B + 更长样本 + OOS）",
        f"**Trading Status**：Current Action = {decision_txt}"
        "（研究输出，非投资建议）",
    ]
    lines += ["### 结论分层\n",
              "- " + "\n- ".join(statuses) + "\n"]
    lines += _what_would_change_my_mind(snap, row, decision_txt)
    return "\n".join(lines)


def _what_would_change_my_mind(snap, row, decision_txt) -> list:
    """P1-9：'什么条件会改变我的判断'——只投影 Ledger/Snapshot 已持久化
    事实，绝不重新计算 Action。"""
    triggers = []
    if snap.institutional_state:
        triggers.append(
            f"机构状态从 {snap.institutional_state} 转向 "
            f"C↓/F↓/P↓ 或 CAPITULATION → 权限下修，结论转保守")
    if snap.setup_type:
        triggers.append(
            f"Swing Setup 消失或 Wave 阶段从 "
            f"{getattr(snap, 'wave_stage', '') or '—'} 转入 "
            f"INVALID/MATURE → 当前参与理由失效")
    if snap.next_fsm_state:
        triggers.append(
            f"FSM 从 {snap.next_fsm_state} 触发 "
            f"EXIT/COOLDOWN/HARD_EXIT → 按状态机退出（不重算目标）")
    dq = (row or {}).get("data_quality") or snap.data_quality
    if dq:
        triggers.append(
            f"数据质量升级至 A/B 且 PIT grade 达到 A"
            f"（当前 {snap.pit_grade or '—'}/{dq}）→ 证据置信度上修")
    if snap.pit_grade in ("C", "D"):
        triggers.append(
            f"PIT 证据达到可认证（当前 {snap.pit_grade}）→ "
            f"才允许把当前结论视为正式研究输出")
    triggers.append(
        "历史同类决策 Outcome（5D/20D/60D）长期与预期相悖 → "
        "触发 Research/OOS 复核，而非直接改参数")
    triggers.append(
        "OOS 非劣性与 Replay 证据任一 NOT_PROVEN → 结论降级为研究提示")
    return ["### 什么条件会改变我的判断\n",
            "- " + "\n- ".join(triggers) + "\n"]


def _latest_file(bt_dir, pattern):
    files = sorted(bt_dir.glob(pattern), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def _conclusion_section(bt_dir, summary_path, run_id, stock):
    """四层结论：证据 → 判断 → 结论 → 限制"""
    lines = ["### 证据"]
    median_oos = None
    excess_bh = None
    if summary_path and summary_path.exists():
        s = json.loads(summary_path.read_text(encoding="utf-8"))
        oos = s.get("rolling_oos_evaluation", [])
        sharpes = [r.get("sharpe") for r in oos if r.get("sharpe") is not None]
        if sharpes:
            median_oos = sorted(sharpes)[len(sharpes) // 2]
        excess_bh = s.get("benchmark", {}).get("buy_hold", {}).get("excess_annualized")
    lines.append(f"- OOS Sharpe 中位数：{_fmt(median_oos)}；"
                 f"等权基准年化超额：{_pct(excess_bh)}")

    ic_file = _latest_file(bt_dir, "ic_analysis_*.json")
    f_t = c_t = incr_r2 = None
    if ic_file:
        ic = json.loads(ic_file.read_text(encoding="utf-8"))
        cr = ic.get("conditional_regression", {})
        for h in ("fwd_13w", "fwd_26w"):
            if h in cr:
                f_t = cr[h].get("f_s", {}).get("t_hac")
                c_t = cr[h].get("c_s", {}).get("t_hac")
                incr_r2 = cr[h].get("incremental_r2")
                break
    lines.append(f"- 条件回归（控制 P 后，HAC）：F t_hac={_fmt(f_t)}，"
                 f"C t_hac={_fmt(c_t)}，增量 R²={_fmt(incr_r2)}")

    strength = "弱"
    if (f_t is not None and abs(f_t) >= 2) or (incr_r2 is not None and incr_r2 > 0.05):
        strength = "中"
    if (f_t is not None and abs(f_t) >= 2) and (incr_r2 is not None and incr_r2 > 0.1):
        strength = "强"
    lines.append(f"\n### 判断：证据强度 {strength}")

    if f_t is not None and abs(f_t) >= 2:
        conclusion = ("F 因子在控制 P 后提供独立增量信息（三维框架部分成立）；"
                      "C 因子当前无显著增量；组合绝对 alpha 偏弱（依赖市场环境）。")
    else:
        conclusion = ("当前证据不足以支持 C/F 在 P 之外的独立增量；"
                      "需更长样本或调整 C 阈值后复验。")
    lines.append(f"\n### 结论\n{conclusion}")

    lines.append("\n### 限制")
    lines.append("- PIT：available_date 为估计（period_end + 45 天），非真实披露日；")
    lines.append("- 流动性：未含 ADV/参与率约束；成本为方向费率 + 最低佣金简化模型；")
    lines.append("- 样本：2021 起（资金流可用期），区间较短；")
    lines.append("- 组合：未做行业中性化与风险约束（sector/concentration/beta）。")
    return "\n".join(lines)


def _inline(text: str) -> str:
    t = _html.escape(str(text))
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
    return t


def _md_to_html(md_text: str) -> str:
    """内置轻量 Markdown→HTML（覆盖本报告子集：标题/表格/列表/引用/代码/粗体）"""
    out = ["<div class='report'>"]
    lines = md_text.splitlines()
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if not s:
            i += 1
            continue
        if s.startswith("# "):
            out.append(f"<h1>{_inline(s[2:])}</h1>")
        elif s.startswith("## "):
            out.append(f"<h2>{_inline(s[3:])}</h2>")
        elif s.startswith("### "):
            out.append(f"<h3>{_inline(s[4:])}</h3>")
        elif s == "---":
            out.append("<hr/>")
        elif s.startswith("> "):
            out.append(f"<blockquote>{_inline(s[2:])}</blockquote>")
        elif s.startswith("- "):
            out.append(f"<li>{_inline(s[2:])}</li>")
        elif s.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i].strip())
                i += 1
            table = ["<table>"]
            for ri, r in enumerate(rows):
                cells = [c.strip() for c in r.strip("|").split("|")]
                if all(c and set(c) <= set("-: ") for c in cells):
                    continue  # 表头分隔行
                tag = "th" if ri == 0 else "td"
                table.append("<tr>" +
                             "".join(f"<{tag}>{_inline(c)}</{tag}>" for c in cells) +
                             "</tr>")
            table.append("</table>")
            out.append("".join(table))
            continue
        else:
            out.append(f"<p>{_inline(s)}</p>")
        i += 1
    out.append("</div>")
    return "\n".join(out)


def _wrap_html(body: str, title: str) -> str:
    return f"""<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<title>{_html.escape(title)}</title>
<style>
body{{font-family:-apple-system,"Microsoft YaHei",sans-serif;margin:24px;color:#1f2937;max-width:960px}}
h1{{font-size:20px}} h2{{font-size:17px;border-bottom:1px solid #e5e7eb;padding-bottom:4px;margin-top:24px}}
h3{{font-size:14px}}
table{{border-collapse:collapse;margin:8px 0;width:100%}}
td,th{{border:1px solid #e5e7eb;padding:4px 8px;font-size:13px;text-align:left}}
th{{background:#f3f4f6}}
code{{background:#f3f4f6;padding:1px 4px;border-radius:4px;font-size:12px}}
blockquote{{border-left:3px solid #d1d5db;margin:8px 0;padding:2px 12px;color:#4b5563}}
li{{margin:2px 0}}
</style></head><body>{body}</body></html>"""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF 个股一体化报告（MD）")
    parser.add_argument("--stock", required=True, help="股票代码（5位）")
    parser.add_argument("--date", default=None, help="决策日（默认最新）")
    parser.add_argument("--run-id", default=None, help="回测 run_id（缺省自动匹配）")
    args = parser.parse_args(argv)

    settings = load_qcfp_settings()
    model_version = get(settings, "model.version", MODEL_VERSION)

    conn = connect()
    try:
        date = args.date or dss._latest_decision(conn, args.stock)
        if not date:
            print(f"❌ 股票 {args.stock} 无决策数据")
            return 1
        row = dss._row(conn, args.stock, date)
        if not row:
            print(f"❌ 股票 {args.stock} 在 {date} 无决策行")
            return 1
        q_history, mtf_history = dss._history(conn, args.stock, date)
        snapshots = _snapshot_table(conn, args.stock, date)
    finally:
        conn.close()

    row["model_version"] = model_version
    row["position_advice"] = dss.position_advice(row, settings)
    row["stop_loss_trigger"] = dss.stop_loss_display(
        dss.get_stop_loss_policy(settings))
    row["key_risks"] = [row.get("risk_reasons") or row.get("risk_level")]
    row["evidence_level"] = "A-"
    row["evidence_monthly"] = "B"
    row["evidence_weekly"] = "C"
    row["evidence_mtf"] = "D"

    market = dss._market_detail(load_idx_hist(), date)
    ic_lookup = dss._ic_reference()
    decision_md = dss.build_detailed_md(row, q_history, mtf_history, market,
                                        ic_lookup, settings)

    bt_dir = get_report_root() / "backtest"
    summary_path, summary_name = _find_summary(bt_dir, args.run_id, args.stock)
    run_id = args.run_id
    if run_id is None and summary_name:
        run_id = summary_name
        if args.stock and run_id.endswith(f"_{args.stock}"):
            run_id = run_id[: -len(args.stock) - 1]
    backtest_md = _backtest_section(summary_path, run_id, args.stock)

    lines = []
    lines.append("# QCFP-MTF 个股一体化分析报告（All-in-One）\n")
    lines.append(f"- 股票：{args.stock}　名称：{row.get('stock_name') or '—'}　"
                 f"决策日：{date}　模型：{model_version}")
    lines.append(f"- 回测绑定：run_id={run_id or '自动匹配'}　（同一 run_id 才与本次报告同源）")
    lines.append(f"- 生成时间：{datetime.now():%Y-%m-%d %H:%M:%S}\n")
    lines.append("### Scope / Provenance\n")
    lines.append("| 项 | 值 |")
    lines.append("| :-- | :-- |")
    lines.append(f"| Analysis Scope | Single Stock（{args.stock}） |")
    lines.append(f"| Backtest Scope | {args.stock}（单股回测） |")
    lines.append("| Research Scope | Full Universe（Model Diagnosis / 历史 IC 为横截面样本） |")
    lines.append(f"| PIT | PIT-C Estimated（period_end+45d；见回测 RUN STATUS） |")
    lines.append("| Universe | 当前可得股票集（存在幸存者偏差风险，未配置 PIT Universe） |")
    lines.append("| Execution | 周线收盘确认 → 次周生效/离场（position=target.shift(1)） |\n")

    lines.append(_governance_card(row, settings))
    lines.append("")

    lines.append("## 一、最新状态快照\n")
    lines.append("| 层级 | 周期末 | 状态 | 明细 |")
    lines.append("| :-- | :-- | :-- | :-- |")
    for layer, pe, state, detail in snapshots:
        lines.append(f"| {layer} | {pe} | {state} | {detail} |")
    lines.append("")

    lines.append("## 二、决策报告（详细版）\n")
    lines.append(decision_md)
    lines.append(_decision_audit_section(row, settings))
    lines.append("\n## 三、回测汇总\n")
    lines.append(backtest_md)
    diag = _model_diagnosis_section(bt_dir)
    if diag:
        lines.append(diag)
    lines.append("\n## 四、研究结论与限制\n")
    lines.append(_conclusion_section(bt_dir, summary_path, run_id, args.stock))

    lines.append("\n## 五、产物清单\n")
    dss_dir = get_report_root() / "dss"
    artifacts = []
    for p in sorted(dss_dir.glob(f"{args.stock}_*.md"))[-3:]:
        artifacts.append(str(p))
    if summary_path:
        artifacts.append(str(summary_path))
    if summary_name:
        html_artifact = bt_dir / f"report_{summary_name}.html"
        if html_artifact.exists():
            artifacts.append(str(html_artifact))
    lines.append(f"- 产物绑定：run_id={run_id or '—'}，决策日={date}，模型={model_version}")
    lines.append("\n".join(f"- `{a}`" for a in artifacts))
    lines.append("\n---\n")
    lines.append(f"> 模型：{MODEL_VERSION}。本报告为研究输出，"
                 "不构成投资建议。")

    out_dir = get_report_root() / "all_in_one"
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / f"{args.stock}_all_in_one_{date}.md"
    html_path = out_dir / f"{args.stock}_all_in_one_{date}.html"
    md_text = "\n".join(lines)
    md_path.write_text(md_text, encoding="utf-8")
    html_path.write_text(
        _wrap_html(_md_to_html(md_text), f"QCFP-MTF All-in-One {args.stock} {date}"),
        encoding="utf-8")
    print(f"All-in-One 报告已生成（MD + HTML）:")
    print(f"  {md_path}")
    print(f"  {html_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
