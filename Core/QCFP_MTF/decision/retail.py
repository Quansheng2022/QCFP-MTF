# coding: utf-8
"""散户波段决策层（Retail Execution Layer）

机构研究层（MTF/DES/C/F/P）继续后台运行；本层只回答散户的四个问题：
    Risk → Regime → Trigger → Position

输出：
    - 红黄绿灯（RED / YELLOW / GREEN）
    - 六态交易阶梯（WAIT/TEST/BUILD/HOLD/REDUCE/EXIT）
    - 散户仓位建议（0%~100%，100% 仅限极强+risk_on 特例）
    - A/B 股票池（趋势持仓池 / 反转观察池）

哲学：Bottom ≠ Buy；Risk Reduction + Structural Improvement + Price Confirmation
      = Buy Permission。红灯 = "我不参与"，不是看空做空。
"""

from ..config.settings import retail_settings

RED_STATES = {"BEARISH_CONFIRMED", "DATA_INSUFFICIENT"}
GREEN_STATES = {"BULLISH_CONFIRMED", "BULLISH_STABLE"}
YELLOW_STATES = {"BULLISH_WARNING", "BEARISH_RECOVERY_CANDIDATE"}

ACTION_FROM_FSM = {
    "FLAT": "WAIT",
    "TESTING": "TEST",
    "BUILDING": "BUILD",
    "HOLDING": "HOLD",
    "TRIMMING": "REDUCE",
    "EXITING": "EXIT",
    "COOLDOWN": "COOLDOWN",
}


def action_from_snapshot(snapshot) -> str:
    """交易阶梯（V31）：由 DecisionSnapshot.next_fsm_state 唯一派生，报告层不重算"""
    return ACTION_FROM_FSM.get(getattr(snapshot, "next_fsm_state", "FLAT"),
                               "WAIT")


def snapshot_light(snapshot) -> str:
    """红黄绿灯（V31）：由 DecisionSnapshot 派生，不再读取 row 重算"""
    nxt = getattr(snapshot, "next_fsm_state", "FLAT")
    perm = getattr(snapshot, "institutional_permission", "WATCH")
    if getattr(snapshot, "exit_event_kind", "NONE") in (
            "HARD_EXIT", "STOP_EXIT", "FORCED_DELEVERAGE") \
            or nxt in ("EXITING", "COOLDOWN") or perm == "BLOCK":
        return "RED"
    if nxt in ("BUILDING", "HOLDING") and perm in ("ALLOW", "STRONG_ALLOW"):
        return "GREEN"
    return "YELLOW"


def position_action_from_snapshot(snapshot) -> str:
    """仓位动作（V32）：权限约束生效时明确展示 NO_RISK_INCREASE，避免语义误读"""
    if getattr(snapshot, "permission_constraint_applied", False):
        return "NO_RISK_INCREASE（权限封顶，维持既有仓位）"
    return "NORMAL（无权限约束）"


def opportunity_level(setup_type, trade_quality) -> str:
    """机会维度：Setup + TQS → Low / Mid / High（不影响 Permission）"""
    if setup_type in (None, "NONE"):
        return "Low"
    tqs = float(trade_quality or 0.0)
    if tqs >= 60:
        return "High"
    if tqs >= 40:
        return "Mid"
    return "Low"


PERMISSION_OPPORTUNITY_MATRIX = {
    "BLOCK": {"Low": "—", "Mid": "—", "High": "—"},
    "WATCH": {"Low": "—", "Mid": "OBS", "High": "OBS"},
    "TEST": {"Low": "—", "Mid": "TEST", "High": "TEST+"},
    "ALLOW": {"Low": "WAIT", "Mid": "TRADE", "High": "STRONG"},
    "STRONG_ALLOW": {"Low": "WAIT", "Mid": "TRADE", "High": "A+"},
}


def opportunity_matrix_md(permission, opportunity) -> str:
    """二维矩阵（行=Permission，列=Opportunity），当前格加粗"""
    lines = ["| Permission \\ Opportunity | Low | Mid | High |",
             "| :-- | :-- | :-- | :-- |"]
    for p in ("BLOCK", "WATCH", "TEST", "ALLOW", "STRONG_ALLOW"):
        cells = []
        for opp in ("Low", "Mid", "High"):
            label = PERMISSION_OPPORTUNITY_MATRIX[p][opp]
            if p == permission and opp == opportunity:
                cells.append(f"**{label}**")
            else:
                cells.append(label)
        lines.append(f"| {p} | {' | '.join(cells)} |")
    return "\n".join(lines)


def traffic_light(row) -> str:
    """红黄绿灯（Legacy 展示辅助，仅供 stock_pool_report 等旧输出使用）"""
    mtf = row.get("mtf_regime")
    risk = row.get("risk_level")
    des = row.get("des_score") or 0
    if mtf in RED_STATES or risk == "Extreme" or des >= 5 \
            or (row.get("tactical_signal") == "Breakdown" and risk == "High"):
        return "RED"
    if mtf in GREEN_STATES and risk in ("Low", "Medium") and des < 5:
        return "GREEN"
    return "YELLOW"


def retail_action(row) -> str:
    """六态交易阶梯：WAIT / TEST / BUILD / HOLD / REDUCE / EXIT"""
    mtf = row.get("mtf_regime")
    risk = row.get("risk_level")
    des = row.get("des_score") or 0
    trig = row.get("tactical_signal")
    if mtf in RED_STATES or risk == "Extreme" or des >= 7:
        return "EXIT"
    if mtf == "BULLISH_WARNING" or risk == "High":
        return "REDUCE"
    if mtf == "BULLISH_CONFIRMED" and risk in ("Low", "Medium"):
        return "BUILD" if trig == "Breakout" else "HOLD"
    if mtf == "BULLISH_STABLE" and risk in ("Low", "Medium"):
        return "HOLD"
    if mtf == "BEARISH_RECOVERY_CANDIDATE" and risk in ("Low", "Medium", "High") \
            and des < 5:
        return "TEST"
    return "WAIT"


def retail_position_band(row, settings) -> str:
    """散户仓位建议（0%~100%；100% 仅限极强 + risk_on 特例）"""
    cfg = retail_settings(settings).get("position_bands", {})
    mtf = row.get("mtf_regime")
    risk = row.get("risk_level")
    if risk == "Extreme" or (row.get("des_score") or 0) >= 7:
        return cfg.get("Extreme", "0%")
    if risk == "High":
        return cfg.get("High", "0%~20%")
    if mtf == "BULLISH_CONFIRMED":
        if row.get("market_context") == "risk_on":
            return cfg.get("strong_risk_on", "80%~100%")
        return cfg.get("BULLISH_CONFIRMED", "60%~80%")
    if mtf == "BULLISH_STABLE":
        return cfg.get("BULLISH_STABLE", "50%~70%")
    if mtf == "BEARISH_RECOVERY_CANDIDATE":
        return cfg.get("Low_recovery", "30%~50%")
    if mtf == "BULLISH_WARNING":
        return cfg.get("REDUCE", "20%~40%")
    return cfg.get("Zero", "0%")


def classify_pool(row, settings) -> str:
    """A 池（趋势持仓池）/ B 池（反转观察池，非立即买）/ None"""
    s = row.get("structural_regime")
    m = row.get("monthly_behavior_state")
    w = row.get("tactical_signal")
    risk = row.get("risk_level")
    des = row.get("des_score") or 0
    conf = row.get("chip_stability_confidence")
    if risk in ("Low", "Medium") and des < 5:
        if s in ("STRUCTURAL_BULLISH", "STRUCTURAL_ACCUMULATION") \
                and m in ("Improving", "Stable") \
                and w in ("Breakout", "Consolidation") \
                and conf in ("High", "Medium"):
            return "A"
        if s in ("STRUCTURAL_DECLINE", "STRUCTURAL_DISTRIBUTION",
                 "STRUCTURAL_BOTTOM_CANDIDATE") \
                and (row.get("q_position_52w") or 1.0) < 0.15 \
                and m == "Improving" and w == "Breakout":
            return "B"
    return None


def retail_card_lines(row, settings) -> list:
    """散户决策卡（V31：只展示 DecisionSnapshot，报告层不再自行决策）

    FSM 状态 / 建议仓位 / 交易阶梯 / 红黄绿灯 / 机构理由全部派生自
    build_report_snapshot（优先 Stateful Shadow，缺失时 FLAT/0 单点推算）。
    """
    from .decision_snapshot import (build_decision_snapshot,
                                    load_canonical_decision)
    from .decision_snapshot import LedgerRequiredError
    try:
        snap, _src = load_canonical_decision(row, settings)
    except LedgerRequiredError as exc:
        return ["## 0.1 散户决策卡（Retail Execution）\n",
                "| 项 | 值 |", "| :-- | :-- |",
                f"| 状态 | ❌ 无正式决策：{exc} |", ""]
    except Exception:
        snap = build_decision_snapshot("FLAT", 0.0, row, settings)
    light = snapshot_light(snap)
    action = action_from_snapshot(snap)
    target = snap.target_position
    emoji = {"RED": "🔴", "YELLOW": "🟡", "GREEN": "🟢"}.get(light, "⚪")
    degrade = (f"（降级:{','.join(snap.institutional_reasons)}）"
               if snap.institutional_reasons else "")
    pos_action = position_action_from_snapshot(snap)
    fsm_extra = "，权限维持态不加仓" if snap.permission_constraint_applied else ""
    budget_txt = (f"{snap.participation_mode}（上限 {snap.participation_cap * 100:.0f}%）"
                  if snap.participation_mode else "—")
    pos_class_txt = {"OBSERVATION": "观察仓（探索性暴露）",
                     "RISK_BEARING": "风险仓",
                     "NONE": "空仓"}.get(snap.position_class, snap.position_class)
    sev_txt = {0: "无", 1: "L1 纪律性", 2: "L2 风险性",
               3: "L3 致命"}.get(snap.exit_severity, snap.exit_severity)
    opportunity = opportunity_level(snap.setup_type, snap.trade_quality)
    matrix = opportunity_matrix_md(snap.institutional_permission, opportunity)
    lines = ["## 0.1 散户决策卡（Retail Execution）\n",
             f"| 项 | 值 |", "| :-- | :-- |",
             f"| 红黄绿灯 | **{emoji} {light}** |",
             f"| 机构状态 | {snap.institutional_state}"
             f"（压力 {snap.institutional_pressure:+d}，"
             f"持续性 {snap.institutional_persistence}）"
             f"→ 权限 **{snap.institutional_permission}**"
             f"（上限 {snap.permission_cap}）{degrade} |",
             f"| 交易状态 | **{action}**（WAIT/TEST/BUILD/HOLD/REDUCE/EXIT/COOLDOWN） |",
             f"| 仓位状态(FSM) | **{snap.next_fsm_state}**"
             f"（{snap.prev_fsm_state}→{snap.next_fsm_state}，"
             "FLAT/TESTING/BUILDING/HOLDING/TRIMMING/EXITING/COOLDOWN"
             f"{fsm_extra}） |",
             f"| 仓位动作 | **{pos_action}** |",
             f"| 决策原因 | **{snap.primary_reason or '—'}**"
             f"（{','.join(snap.secondary_reasons) if snap.secondary_reasons else '无'}） |",
             f"| Trade Quality | **{snap.trade_quality:.0f} / 100"
             f"（{snap.trade_quality_band or '—'}）** |",
             f"| 参与预算 | **{budget_txt}**　仓位类别 **{pos_class_txt}**　"
             f"退出等级 **{sev_txt}** |",
             f"| 建议仓位 | **{target * 100:.0f}%**（决策链 target；"
             f"矩阵基准 {snap.base_fsm_state}） |",
             f"| 趋势 | {row.get('monthly_behavior_state') or '—'} ｜ "
             f"周线 {row.get('tactical_signal') or '—'} ｜ "
             f"资金 {row.get('f_state') or '—'} ｜ "
             f"筹码 {row.get('chip_stability_confidence') or '—'} |",
             f"| 风险 | {row.get('risk_level') or '—'}（DES={row.get('des_score') or 0} "
             f"{row.get('des_band') or '—'}） |\n"]
    lines += ["**Permission × Opportunity 矩阵**\n", matrix, "\n"]
    if light == "RED":
        lines += ["**禁止**：✕ 抄底　✕ 因跌幅巨大补仓　✕ 因估值便宜提前下注",
                  "**重新观察**：Monthly Improving → Weekly Breakout → Risk ≤ Medium\n"]
    elif action == "TEST":
        lines += ["**试仓纪律**：首次允许下注（10~20%），Breakout 确认后才加仓；"
                  "止损=建仓周最低价×(1-buffer)\n"]
    elif action in ("BUILD", "HOLD"):
        lines += ["**持有纪律**：回调不破位不加不减；周线 Breakdown 或 DES≥7 立即退出\n"]
    return lines
