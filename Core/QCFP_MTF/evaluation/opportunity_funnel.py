# coding: utf-8
"""Opportunity Funnel（QCFP-MTF 2.8：67 号机会漏斗）

把"为什么没有交易"拆开：
    Universe → PIT Valid → Permission Eligible → Wave Candidate →
    FSM Eligible → Risk Eligible → Liquidity Eligible → Final Trade

验收标准：系统必须能解释机会是在哪里被过滤掉的，
而不是只显示最终几只股票。
"""


FUNNEL_STAGES = ("universe", "pit_valid", "permission_eligible",
                 "wave_candidate", "fsm_eligible", "risk_eligible",
                 "liquidity_eligible", "final_trade")


def opportunity_funnel(stage_counts: dict) -> dict:
    """stage_counts：{stage: n}（按 FUNNEL_STAGES 顺序递减）。"""
    counts = {s: int(stage_counts.get(s) or 0)
              for s in FUNNEL_STAGES}
    drops, max_drop, bottleneck = [], 0.0, None
    for i in range(1, len(FUNNEL_STAGES)):
        prev, cur = FUNNEL_STAGES[i - 1], FUNNEL_STAGES[i]
        incoming = counts[prev]
        remaining = counts[cur]
        drop_ratio = round(1 - remaining / incoming, 4) \
            if incoming else None
        drops.append({"stage": cur, "from": prev,
                      "incoming": incoming, "remaining": remaining,
                      "drop_ratio": drop_ratio})
        if drop_ratio is not None and drop_ratio > max_drop:
            max_drop, bottleneck = drop_ratio, cur
    return {"counts": counts, "drops": drops,
            "bottleneck": bottleneck,
            "bottleneck_drop_ratio": round(max_drop, 4)}


def funnel_verdict(funnel: dict) -> dict:
    bottleneck = funnel.get("bottleneck")
    if bottleneck == "permission_eligible":
        return {"verdict": "PERMISSION_TOO_STRICT",
                "guidance": "机会大量在 Permission 环节被过滤，"
                            "检查权限阈值"}
    if bottleneck == "wave_candidate":
        return {"verdict": "WAVE_TOO_NARROW",
                "guidance": "Wave 候选过少，检查 Wave 触发宽度"}
    if bottleneck in ("risk_eligible", "liquidity_eligible"):
        return {"verdict": "PORTFOLIO_OR_LIQUIDITY_BOTTLENECK",
                "guidance": "风险/流动性环节成为瓶颈，检查组合约束"}
    if bottleneck is None:
        return {"verdict": "NO_DATA", "guidance": "缺少漏斗数据"}
    return {"verdict": "NORMAL",
            "guidance": f"机会主要在 {bottleneck} 环节被过滤"}


def opportunity_funnel_from_snapshots(snapshots) -> dict:
    """新 19 号：stage counts 直接来自真实 DecisionSnapshot /
    ConstraintTrace / Ledger，而不是重新跑一套筛选逻辑。

    漏斗是累积口径：只有通过前面所有 stage 的快照才能进入下一 stage，
    因此每个 stage 计数单调不增，能回答"机会在哪里被过滤"。
    """
    counts = {s: 0 for s in FUNNEL_STAGES}
    snapshots = list(snapshots or [])
    counts["universe"] = len(snapshots)
    stage_checks = (
        ("pit_valid",
         lambda s: (getattr(s, "pit_grade", "") or "") in ("A", "B")),
        ("permission_eligible",
         lambda s: (getattr(s, "institutional_permission", "") or "")
         in ("TEST", "ALLOW", "STRONG_ALLOW")),
        ("wave_candidate",
         lambda s: bool(getattr(s, "wave_stage", ""))),
        ("fsm_eligible",
         lambda s: (getattr(s, "next_fsm_state", "") or "") != "FLAT"),
        ("risk_eligible",
         lambda s: (getattr(s, "risk_level", "") or "") in
         ("", "Low", "Medium")),   # 缺失风险数据不阻塞漏斗诊断
        ("liquidity_eligible",
         lambda s: (getattr(s, "binding_constraint", "") or "")
         not in ("liquidity_cap", "execution_cap")),
        ("final_trade",
         lambda s: float(getattr(s, "target_position", 0.0)
                         or 0.0) > 1e-9),
    )
    for s in snapshots:
        eligible = True
        for stage, check in stage_checks:
            if eligible and check(s):
                counts[stage] += 1
            else:
                eligible = False
    return opportunity_funnel(counts)


def funnel_from_ledger(ledger_rows) -> dict:
    """新 67 号：Funnel 数字必须来自 Canonical Ledger / ConstraintTrace /
    DecisionSnapshot，不能让 Funnel 自己再跑一套筛选逻辑。"""
    counts = {s: 0 for s in FUNNEL_STAGES}
    rows = list(ledger_rows or [])
    counts["universe"] = len(rows)
    stage_checks = (
        ("pit_valid",
         lambda r: (r.get("pit_grade") or "") in ("A", "B")),
        ("permission_eligible",
         lambda r: (r.get("institutional_permission") or "")
         in ("TEST", "ALLOW", "STRONG_ALLOW")),
        ("wave_candidate",
         lambda r: bool(r.get("wave_stage"))),
        ("fsm_eligible",
         lambda r: (r.get("next_fsm_state") or "") != "FLAT"),
        ("risk_eligible",
         lambda r: (r.get("risk_level") or "") in
         ("", "Low", "Medium")),
        ("liquidity_eligible",
         lambda r: (r.get("binding_constraint") or "")
         not in ("liquidity_cap", "execution_cap")),
        ("final_trade",
         lambda r: float(r.get("final_target") or 0.0) > 1e-9),
    )
    for r in rows:
        eligible = True
        for stage, check in stage_checks:
            if eligible and check(r):
                counts[stage] += 1
            else:
                eligible = False
    return opportunity_funnel(counts)


def no_trade_explanation(snapshot) -> dict:
    """新 67 号：任意 NO_TRADE 明确回答"在哪一层退出 Funnel + 为什么"。"""
    from ..monitoring.critical_path_observability import \
        decision_layer_outcome
    outcome = decision_layer_outcome(snapshot)
    target = float(getattr(snapshot, "target_position", 0.0) or 0.0)
    if target > 1e-9:
        return {"no_trade": False, "outcome": "TRADE"}
    binding = getattr(snapshot, "binding_constraint", "") or ""
    filtered_at = outcome.get("filtered_at")
    why = f"过滤层: {filtered_at}" if filtered_at else \
        f"可信判断无机会（binding={binding or 'none'}）"
    return {"no_trade": True, "filtered_at": filtered_at,
            "binding_constraint": binding, "why": why,
            "layer": outcome.get("layer")}
