#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF P5 —— 个股 DSS 详细分析报告生成器

按股票 + 决策日输出：
- 标准 JSON（规格书第七章协议）
- 详细 Markdown（决策摘要 / 季度结构 / 月线行为 / 周线触发 / 成本位置 /
  置信度证据 / 风险与市场环境 / 历史状态时间线 / 状态前向收益对照 / 数据质量）

用法：
    python Core/QCFP_MTF/scripts/dss_report.py --stock 00700 [--date 2026-08-14]
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

import pandas as pd

from QCFP_MTF.common.db import connect
from QCFP_MTF.common.logger import setup_logger
from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.config.settings import DEFAULT_SETTINGS, get, load_qcfp_settings
from QCFP_MTF.data.loader import load_idx_hist
from QCFP_MTF.decision.dss_output import build_dss_json
from QCFP_MTF.decision.versions import MODEL_VERSION
from QCFP_MTF.decision.retail import retail_card_lines
from QCFP_MTF.decision.stop_loss import get_stop_loss_policy, stop_loss_display


def _latest_decision(conn, stock):
    return conn.execute(
        "SELECT MAX(decision_date) FROM qcfp_mtf_decision WHERE stock_code=?", (stock,)
    ).fetchone()[0]


def _row(conn, stock, date):
    r = conn.execute(
        "SELECT * FROM qcfp_mtf_decision WHERE stock_code=? AND decision_date=?",
        (stock, date)).fetchone()
    if not r:
        return None
    d = dict(r)
    qs = conn.execute(
        """SELECT core_score, c_state, f_state, p_state,
                  inst_ownership_pct_chg, holder_quantity_chg_pct,
                  inst_participation_chg, q_inst_flow_raw, q_inst_flow_z,
                  q_ifa_zscore, q_return, q_trend_score, q_position_52w,
                  resolve_method, available_date, data_quality
           FROM qcfp_quarterly_structural
           WHERE stock_code=? AND available_date<=?
           ORDER BY period_end DESC LIMIT 1""",
        (stock, date)).fetchone()
    mb = conn.execute(
        """SELECT m_vp_regime, turnover_liquidity_regime,
                  m_turnover_zscore, m_turnover_pctl, m_turnover_ma_ratio,
                  m_volume_ma_ratio, m_volume_accel, m_turnover_efficiency,
                  cbi_state, cost_vs_weekly_vwap, cost_vs_monthly_vwap,
                  cost_vs_quarterly_vwap, data_quality
           FROM qcfp_monthly_behavior
           WHERE stock_code=? AND month_end<=? ORDER BY month_end DESC LIMIT 1""",
        (stock, date)).fetchone()
    wt = conn.execute(
        """SELECT w_breakout, w_breakdown, w_turnover_spike, w_volume_breakout,
                  w_volume_shrink, w_vwap_deviation, w_ma_slope, w_turnover_deviation,
                  data_quality
           FROM qcfp_weekly_tactical WHERE stock_code=? AND week_end=?""",
        (stock, date)).fetchone()
    def _suffix(src, suffix):
        out = dict(src) if src else {}
        if "data_quality" in out:
            out[f"data_quality{suffix}"] = out.pop("data_quality")
        return out

    d.update(_suffix(qs, "_q"))
    d.update(_suffix(mb, "_m"))
    d.update(_suffix(wt, "_w"))
    dt = conn.execute(
        "SELECT trade_date, daily_state FROM qcfp_daily_tactical "
        "WHERE stock_code=? AND trade_date<=? ORDER BY trade_date DESC LIMIT 1",
        (stock, date)).fetchone()
    if dt:
        d["daily_date"] = dt["trade_date"]
        d["daily_state"] = dt["daily_state"]
    if not d.get("stock_name"):
        nm = conn.execute(
            "SELECT stock_name FROM hk_stock_info WHERE stock_code=?", (stock,)).fetchone()
        if nm and nm[0]:
            d["stock_name"] = nm[0]
    return d


def _history(conn, stock, date, n=8):
    q = [dict(x) for x in conn.execute(
        """SELECT period_end, structural_regime, core_score, c_state, f_state, p_state
           FROM qcfp_quarterly_structural
           WHERE stock_code=? AND available_date<=?
           ORDER BY period_end DESC LIMIT ?""", (stock, date, n)).fetchall()]
    m = [dict(x) for x in conn.execute(
        """SELECT decision_date, mtf_regime, action_signal, risk_level
           FROM qcfp_mtf_decision
           WHERE stock_code=? AND decision_date<=?
           ORDER BY decision_date DESC LIMIT ?""", (stock, date, n)).fetchall()]
    return q, m


def _market_detail(idx_df, date):
    idx = idx_df[["date", "HSI", "VHSI"]].copy()
    idx["date"] = pd.to_datetime(idx["date"])
    idx = idx.sort_values("date").dropna(subset=["HSI"])
    idx["hsi_ret_60d"] = idx["HSI"] / idx["HSI"].shift(60) - 1.0
    asof = pd.DataFrame({"date": pd.to_datetime([date])})
    m = pd.merge_asof(asof, idx, on="date", direction="backward")
    if m.empty or pd.isna(m.iloc[0]["HSI"]):
        return None
    return {"hsi": float(m.iloc[0]["HSI"]),
            "hsi_ret_60d": float(m.iloc[0]["hsi_ret_60d"]),
            "vhsi": float(m.iloc[0]["VHSI"])}


def _ic_reference():
    """读取最新 IC 分析中的结构状态前向收益表，返回 {(state, horizon): stats}"""
    backtest_dir = get_report_root() / "backtest"
    files = sorted(backtest_dir.glob("ic_analysis_*.json")) if backtest_dir.exists() else []
    if not files:
        return {}
    data = json.loads(files[-1].read_text(encoding="utf-8"))
    lookup = {}
    states = data.get("states", {}).get("结构状态", {})
    for horizon, records in states.items():
        for rec in records:
            state = rec.get("structural_regime")
            if not state:
                continue
            lookup[(state, horizon)] = rec
    return lookup


def _fmt(value, digits=4):
    if value is None:
        return "—"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def position_advice(row, settings) -> str:
    """仓位建议（P0-C 新 7 号）：只读 Snapshot/Ledger 事实，禁止重算。

    优先 canonical final_target；无 canonical 时展示 Legacy target
    并标注 Legacy，绝不调用 sizing 引擎重新计算。
    """
    final_target = row.get("final_target")
    if final_target is None:
        final_target = row.get("target_position")
    if final_target is None:
        final_target = row.get("target")
    if final_target is None:
        return "—"
    try:
        pct = f"{float(final_target) * 100:.0f}%"
    except (TypeError, ValueError):
        return "—"
    if row.get("final_target") is not None \
            or row.get("target_position") is not None:
        return f"{pct}（Canonical FinalTarget）"
    return f"{pct}（Legacy target，仅供对照）"


def display_action(row) -> str:
    """行动显示（P0-C 新 7 号）：报告解释事实，不制造事实。

    CanonicalAction 原样展示（如 REDUCE），战术试多的语义
    由 trade_interpretation 单独解释，禁止改写 Canonical 动作。
    """
    return row.get("action_signal") or "—"


def trade_intent(row) -> str:
    """交易意图（P0-C 新 7 号）：与 CanonicalAction 一致，不改写。"""
    return row.get("action_signal") or "—"


def trade_interpretation(row) -> str:
    """解释层（非改写）：战术试多条件存在时说明 REDUCE 的语义背景。"""
    if row.get("align_method") == "tactical_override" \
            or bool(row.get("is_override")):
        return "Tactical test condition existed（空头结构下的试多观察）"
    return ""


def strategic_position(row) -> str:
    """战略定位（由季度结构推导）：LONG / BEARISH / NEUTRAL"""
    s = row.get("structural_regime")
    if s in ("STRUCTURAL_BULLISH", "STRUCTURAL_ACCUMULATION"):
        return "LONG"
    if s in ("STRUCTURAL_DECLINE", "STRUCTURAL_DISTRIBUTION"):
        return "BEARISH"
    return "NEUTRAL"   # DIVERGENCE / BOTTOM_CANDIDATE / 缺失


def tactical_hint(row) -> str:
    """日线时机提示（L4）：Daily 只定时机，不改变战略方向"""
    st = row.get("daily_state")
    if st == "DAILY_BREAKOUT":
        return "日线突破：允许早入场/战术加仓"
    if st == "DAILY_ACCUMULATION":
        return "日线吸筹：潜在突破，可关注"
    if st == "DAILY_PULLBACK":
        return "日线回调：持有/等待回踩确认，不减仓"
    if st == "DAILY_DISTRIBUTION":
        return "日线派发：战术减仓/警戒"
    if st == "DAILY_DECLINE":
        return "日线持续下降：下行风险证据，减仓/退出"
    return "日线中性：等待触发"


def _pct(value, digits=2):
    if value is None or value != value:
        return "—"
    return f"{float(value) * 100:.{digits}f}%"


def _num2(value):
    """保留 2 位小数的数值显示（如 CBI）"""
    if value is None or value != value:
        return "—"
    return f"{float(value):.2f}"


def build_detailed_md(row, q_history, mtf_history, market, ic_lookup,
                      settings=None) -> str:
    if settings is None:
        settings = DEFAULT_SETTINGS
    lines = []
    lines.append("# QCFP-MTF 个股决策分析报告（详细版）\n")
    lines.append(f"- 股票：{row.get('stock_code')}　名称：{row.get('stock_name') or '—'}")
    lines.append(f"- 决策日：{row.get('decision_date')}　模型：{row.get('model_version')}")
    lines.append(f"- 综合数据质量：{row.get('data_quality') or '—'}"
                 f"（季度 {row.get('data_quality_q') or '—'} / "
                 f"月线 {row.get('data_quality_m') or '—'} / "
                 f"周线 {row.get('data_quality_w') or '—'}）\n")

    lines.append("## 0. 决策卡（Decision Card）\n")
    lines.append("| 层 | 当前状态 |")
    lines.append("| :-- | :-- |")
    lines.append(f"| Strategic Regime | **{strategic_position(row)}** |")
    lines.append(f"| Structural | **{row.get('structural_regime') or '—'}**"
                 f"（core={_fmt(row.get('core_score'))}） |")
    lines.append(f"| Behavioral | **{row.get('monthly_behavior_state') or '—'}** |")
    lines.append(f"| Tactical Trigger | **{row.get('tactical_signal') or '—'}** |")
    lines.append(f"| Tactical Opportunity | **{trade_intent(row)}** |")
    if trade_interpretation(row):
        lines.append(f"| 解释 | {trade_interpretation(row)} |")
    lines.append(f"| Risk | **{row.get('risk_level') or '—'}** |")
    lines.append(f"| Position（Legacy A0） | **{row.get('position_advice') or '—'}** |\n")
    des = row.get("des_score")
    if des is not None:
        override = "ACTIVE" if (row.get("risk_floor") or (des >= 5)) else "INACTIVE"
        lines.append(f"**DOWNTREND EVIDENCE**：DES = {des}（{row.get('des_band') or '—'}）"
                     f"｜**Tactical Risk Override: {override}**\n")
    lines.append(f"**WHY**：季度 {row.get('structural_regime') or '—'} / "
                 f"月线 {row.get('monthly_behavior_state') or '—'} / "
                 f"周线 {row.get('tactical_signal') or '—'} / "
                 f"日线 {row.get('daily_state') or '—'}")
    lines.append(f"**INVALIDATION**：{row.get('stop_loss_trigger') or '—'}")
    lines.append(f"**CONFIDENCE**：{row.get('chip_stability_confidence') or '—'} "
                 f"/ Evidence {row.get('evidence_mtf') or 'D'}（模型结果，非收益预测）\n")
    lines += retail_card_lines(row, settings)

    lines.append("## 1. 决策摘要\n")
    lines.append("| 维度 | 结论 |")
    lines.append("| :-- | :-- |")
    lines.append(f"| MTF 状态 | **{row.get('mtf_regime') or '—'}** |")
    lines.append(f"| Action Signal | **{row.get('action_signal') or '—'}** |")
    lines.append(f"| Alignment Override | **{str(row.get('align_method') == 'tactical_override')}** |")
    base_a = row.get("base_action")
    if base_a:
        lines.append(f"| Base → Final | **{base_a} → {row.get('action_signal') or '—'}** |")
    lines.append(f"| Trade Intent | **{trade_intent(row)}** |")
    lines.append(f"| 战略 × 战术 | **{strategic_position(row)}** × {display_action(row)} |")
    lines.append(f"| State Score | {row.get('qcfp_score') if row.get('qcfp_score') is not None else '—'}"
                 f"（状态编码，State-First，非连续预测分数/非收益概率） |")
    cqs = row.get("catalyst_score")
    lines.append(f"| 催化剂质量评分 | {cqs if cqs is not None else '—'}（{row.get('catalyst_type') or '—'}） |")
    lines.append(f"| 风险等级 | **{row.get('risk_level') or '—'}** |")
    lines.append(f"| 仓位建议（Legacy A0） | {row.get('position_advice') or '—'} |")
    lines.append(f"| 止损触发 | {row.get('stop_loss_trigger') or '—'} |\n")

    lines.append("## 2. 季度结构（Layer 1 · Structural）\n")
    lines.append(f"**状态**：{row.get('structural_regime') or '—'}（core_score = "
                 f"{_fmt(row.get('core_score'))}，证据 {row.get('evidence_level') or '—'}，"
                 f"解析方式 {row.get('resolve_method') or '—'}，披露日 {row.get('available_date') or '—'}）\n")
    lines.append("| C/F/P 状态 | 原始因子 | 数值 |")
    lines.append("| :-- | :-- | :-- |")
    lines.append(f"| {row.get('c_state') or '—'} | 机构持股比例环比（pp） | {_fmt(row.get('inst_ownership_pct_chg'))} |")
    lines.append(f"| {row.get('c_state') or '—'} | 持股数量环比（%） | {_fmt(row.get('holder_quantity_chg_pct'))} |")
    lines.append(f"| {row.get('c_state') or '—'} | 机构数量环比（%） | {_fmt(row.get('inst_participation_chg'))} |")
    lines.append(f"| {row.get('f_state') or '—'} | 机构资金净流入 Z | {_fmt(row.get('q_inst_flow_z'))} |")
    lines.append(f"| {row.get('f_state') or '—'} | IFA Z-Score | {_fmt(row.get('q_ifa_zscore'))} |")
    q_ret = row.get("q_return")
    lines.append(f"| {row.get('p_state') or '—'} | 季度收益 | {_pct(q_ret / 100 if q_ret is not None else None)} |")
    lines.append(f"| {row.get('p_state') or '—'} | Trend Score | {_fmt(row.get('q_trend_score'))} |")
    lines.append(f"| {row.get('p_state') or '—'} | 52 周位置 | {_fmt(row.get('q_position_52w'))} |\n")

    lines.append("## 3. 月线行为（Layer 2 · Stage）\n")
    lines.append(f"**状态**：{row.get('monthly_behavior_state') or '—'}（证据 B）｜"
                 f"VP：{row.get('m_vp_regime') or '—'}｜换手：{row.get('turnover_liquidity_regime') or '—'}｜"
                 f"CBI：{_num2(row.get('cbi_score'))}（{row.get('cbi_state') or '—'}）\n")
    lines.append("| 指标 | 数值 |")
    lines.append("| :-- | :-- |")
    lines.append(f"| 换手率 Z-Score | {_fmt(row.get('m_turnover_zscore'))} |")
    lines.append(f"| 换手率百分位 | {_fmt(row.get('m_turnover_pctl'))} |")
    lines.append(f"| 换手率/MA6 | {_fmt(row.get('m_turnover_ma_ratio'))} |")
    lines.append(f"| 成交量/MA6 | {_fmt(row.get('m_volume_ma_ratio'))} |")
    lines.append(f"| 量加速度 | {_fmt(row.get('m_volume_accel'))} |")
    lines.append(f"| 换手效率 | {_fmt(row.get('m_turnover_efficiency'))} |\n")

    lines.append("## 4. 周线触发（Layer 3 · Trigger）\n")
    lines.append(f"**信号**：{row.get('tactical_signal') or '—'}（证据 C）\n")
    lines.append("| 指标 | 数值 |")
    lines.append("| :-- | :-- |")
    lines.append(f"| 有效突破 | {row.get('w_breakout') or 0} |")
    lines.append(f"| 有效破位 | {row.get('w_breakdown') or 0} |")
    lines.append(f"| 放量突破 | {row.get('w_volume_breakout') or 0} |")
    lines.append(f"| 极度缩量 | {row.get('w_volume_shrink') or 0} |")
    lines.append(f"| 极端换手 | {row.get('w_turnover_spike') or 0} |")
    lines.append(f"| 换手偏离（vs 季度周均） | {_pct(row.get('w_turnover_deviation'))} |")
    lines.append(f"| 周 VWAP 偏离 | {_pct(row.get('w_vwap_deviation'))} |")
    lines.append(f"| 均线斜率 | {row.get('w_ma_slope') or '—'} |\n")

    lines.append("## 4.5 日线战术层（L4 · Tactical Timing）\n")
    lines.append(f"**日线状态**：{row.get('daily_state') or '—'}"
                 f"（截至 {row.get('daily_date') or '—'}）\n")
    lines.append(f"**时机提示**：{tactical_hint(row)}\n")
    lines.append("> 定位：Q/M/W 决定战略方向，Daily 只负责交易时机（不改变 Q/M/W 状态）；"
                 "日线状态/资金流已作为下行风险证据进入 DES（`daily.risk` 生效），"
                 "`daily.timing`（买入时机）仍默认关闭。\n")

    lines.append("## 5. 成本位置\n")
    lines.append(f"**状态**：{row.get('cost_position') or '—'}\n")
    lines.append("| 周期 VWAP | 偏离 |")
    lines.append("| :-- | :-- |")
    lines.append(f"| 周 | {_pct(row.get('cost_vs_weekly_vwap'))} |")
    lines.append(f"| 月 | {_pct(row.get('cost_vs_monthly_vwap'))} |")
    lines.append(f"| 季 | {_pct(row.get('cost_vs_quarterly_vwap'))} |\n")

    lines.append("## 6. 置信度与证据\n")
    lines.append(f"- 筹码稳定置信度：**{row.get('chip_stability_confidence') or '—'}**"
                 f"（60%×季度筹码评分 + 40%×CBI，权重已归一化）")
    lines.append(f"- 结构-行为对齐：{row.get('structure_behavior_alignment') or '—'}")
    lines.append(f"- MTF 证据等级：{row.get('evidence_mtf') or 'D'}（模型组合结果，仅供决策参考）")
    lines.append(f"- 证据摘要：{row.get('evidence_summary') or '—'}\n")

    lines.append("## 7. 风险与市场环境\n")
    lines.append(f"- 风险等级：**{row.get('risk_level') or '—'}**"
                 f"（综合 MTF 状态、背离、市场环境、数据质量、置信度）")
    lines.append(f"- 市场环境：{row.get('market_context') or '—'}")
    if row.get("catalyst_type") == "纯脉冲/噪音":
        lines.append("- 催化剂提示：纯脉冲/噪音行情，观察仓上限 5%，2 周时间止损")
    elif row.get("catalyst_type") == "中性偏强":
        lines.append("- 催化剂提示：中性偏强，观察仓 20%，移动止损（收盘跌破建仓周最低价离场）")
    elif row.get("catalyst_type") == "高质量反转":
        lines.append("- 催化剂提示：高质量反转，观察仓 35%，可持有至季线结构确认")
    if market:
        lines.append(f"- HSI：{_fmt(market.get('hsi'), 0)}　60 日收益：{_pct(market.get('hsi_ret_60d'))}"
                     f"　VHSI：{_fmt(market.get('vhsi'), 2)}")
    lines.append("")

    lines.append("## 8. 历史状态时间线\n")
    if q_history:
        lines.append("### 季度结构（近 8 期）")
        lines.append("| 季度末 | 状态 | Score | C | F | P |")
        lines.append("| :-- | :-- | :-- | :-- | :-- | :-- |")
        for r in q_history:
            lines.append(f"| {r.get('period_end')} | {r.get('structural_regime')} | "
                         f"{_fmt(r.get('core_score'))} | {r.get('c_state') or '—'} | "
                         f"{r.get('f_state') or '—'} | {r.get('p_state') or '—'} |")
        lines.append("")
    if mtf_history:
        lines.append("### MTF 决策（近 8 周）")
        lines.append("| 决策日 | MTF 状态 | Action | 风险 |")
        lines.append("| :-- | :-- | :-- | :-- |")
        for r in mtf_history:
            lines.append(f"| {r.get('decision_date')} | {r.get('mtf_regime')} | "
                         f"{r.get('action_signal') or '—'} | {r.get('risk_level') or '—'} |")
        lines.append("")

    lines.append("## 9. 状态前向收益对照（历史 IC 证据）\n")
    state = row.get("structural_regime")
    found = False
    for horizon in ("fwd_4w", "fwd_13w", "fwd_26w"):
        rec = ic_lookup.get((state, horizon))
        if rec:
            found = True
            label = horizon.replace("fwd_", "前向 ").replace("w", " 周")
            lines.append(f"- {state} @ {label}：历史均值 {_pct(rec.get('mean_fwd'))}，"
                         f"中位数 {_pct(rec.get('median_fwd'))}，"
                         f"命中率 {_pct(rec.get('hit_rate'))}（样本 {rec.get('n')}）")
    if not found:
        lines.append("- 暂无该状态的 IC 对照数据（可先运行 `ic_analysis.py` 生成）。")
    lines.append("")

    lines.append("## 10. 数据质量与合规\n")
    lines.append("| 层级 | 证据等级 | 数据质量 |")
    lines.append("| :-- | :-- | :-- |")
    lines.append(f"| 季度结构（C/F/P 派生复合） | {row.get('evidence_level') or 'A-'} | {row.get('data_quality_q') or '—'} |")
    lines.append(f"| 月线行为 | {row.get('evidence_monthly') or 'B'} | {row.get('data_quality_m') or '—'} |")
    lines.append(f"| 周线触发 | {row.get('evidence_weekly') or 'C'} | {row.get('data_quality_w') or '—'} |")
    lines.append(f"| MTF 决策 | {row.get('evidence_mtf') or 'D'} | {row.get('data_quality') or '—'} |")
    lines.append("\n> 注：证据等级描述数据的**性质**（A 直接事实 / A- 派生 / B 行为代理 / C 短周期 / D 模型结果）；"
                 "数据质量描述数据的**完整度**（A~D）。二者独立，互不替代。")
    lines.append(f"\n- Anti-Inference 检查：{row.get('ai_check') or 'PASSED'}\n")
    lines.append("---\n")
    lines.append(f"> 模型：{MODEL_VERSION}"
                 "（State-First, Score-Second；层级不可越权）。"
                 "本报告为研究输出，不构成投资建议；"
                 "证据等级与数据质量详见各层标注。")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF 个股 DSS 详细报告")
    parser.add_argument("--stock", required=True, help="股票代码（5位）")
    parser.add_argument("--date", help="决策日（默认最新）")
    args = parser.parse_args(argv)

    settings = load_qcfp_settings()
    model_version = get(settings, "model.version", MODEL_VERSION)
    logger = setup_logger("dss_report", log_file=f"dss_report_{args.stock}.log", mode="a")

    conn = connect()
    try:
        date = args.date or _latest_decision(conn, args.stock)
        if not date:
            logger.error(f"股票 {args.stock} 无决策数据")
            return 1
        row = _row(conn, args.stock, date)
        if not row:
            logger.error(f"股票 {args.stock} 在 {date} 无决策行")
            return 1
        q_history, mtf_history = _history(conn, args.stock, date)
    finally:
        conn.close()

    row["model_version"] = model_version
    row["position_advice"] = position_advice(row, settings)
    row["stop_loss_trigger"] = stop_loss_display(get_stop_loss_policy(settings))
    row["key_risks"] = [row.get("risk_reasons") or row.get("risk_level")]
    # 证据等级与数据质量是二维独立体系（证据=数据性质，质量=数据完整度）
    row["evidence_level"] = "A-"      # 季度结构为 C/F/P 派生复合
    row["evidence_monthly"] = "B"     # 月线行为代理
    row["evidence_weekly"] = "C"      # 周线短周期信号
    row["evidence_mtf"] = "D"         # MTF 为模型组合结果

    market = _market_detail(load_idx_hist(), date)
    ic_lookup = _ic_reference()

    dss = build_dss_json(row, settings)
    out_dir = get_report_root() / "dss"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{args.stock}_{date}.json"
    md_path = out_dir / f"{args.stock}_{date}.md"
    json_path.write_text(json.dumps(dss, ensure_ascii=False, indent=2, default=str),
                         encoding="utf-8")
    md_path.write_text(build_detailed_md(row, q_history, mtf_history,
                                         market, ic_lookup),
                       encoding="utf-8")

    d = dss["decision"]
    logger.info(f"详细报告已生成: {json_path} / {md_path}")
    print(f"DSS: {args.stock} {date} → {d['mtf_regime']} / {d['action']} / "
          f"risk={dss['risk']['risk_level']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
