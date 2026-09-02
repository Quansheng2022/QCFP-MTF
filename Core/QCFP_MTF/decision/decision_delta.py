# coding: utf-8
"""DecisionDelta（QCFP-MTF 2.8：24 号决策变化解释）

回答"昨天 HOLD，今天为什么变 REDUCE"：
    Previous Target vs Current Target →
    WHAT CHANGED / WHY CHANGED / WHO CAUSED CHANGE /
    WHETHER RISK INCREASED / BINDING CONSTRAINT

每次 target_t != target_t-1 必须产生 machine-readable DecisionDelta。
"""


def decision_delta(previous, current, binding_constraint="") -> dict:
    """previous/current：{target_position, permission, setup_type,
    next_fsm_state, risk_level, exit_event_kind}"""
    get = lambda d, k: d.get(k) if isinstance(d, dict) else \
        getattr(d, k, None)
    prev_target = float(get(previous, "target_position") or 0.0)
    curr_target = float(get(current, "target_position") or 0.0)
    delta = curr_target - prev_target
    changes = []
    for key, label in (("permission", "Permission"),
                       ("setup_type", "Wave"),
                       ("wave_stage", "Wave Stage"),
                       ("next_fsm_state", "FSM"),
                       ("risk_level", "Risk"),
                       ("exit_event_kind", "Exit"),
                       ("participation_mode", "Participation"),
                       ("liquidity_cap", "Liquidity Cap"),
                       ("risk_cap", "Risk Cap")):
        pv, cv = get(previous, key), get(current, key)
        if pv != cv:
            changes.append(f"{label}: {pv} → {cv}")
    risk_increased = delta > 1e-9
    return {
        "previous_target": round(prev_target, 4),
        "current_target": round(curr_target, 4),
        "target_delta": round(delta, 4),
        "changed": bool(changes) or abs(delta) > 1e-9,
        "what_changed": changes,
        "why_changed": get(current, "primary_reason")
        or get(current, "reason", ""),
        "who_caused_change": binding_constraint or "raw_target",
        "risk_increased": risk_increased,
        "binding_constraint": binding_constraint,
    }


def delta_completeness(delta: dict) -> dict:
    """新 24 号：只要 target_t != target_t-1 就必须有
    WHAT_CHANGED / WHY_CHANGED / BINDING_CONSTRAINT。"""
    target_changed = abs(float(delta.get("target_delta") or 0.0)) > 1e-9
    missing = []
    if not delta.get("what_changed"):
        missing.append("WHAT_CHANGED")
    if not delta.get("why_changed"):
        missing.append("WHY_CHANGED")
    if not delta.get("binding_constraint"):
        missing.append("BINDING_CONSTRAINT")
    complete = not missing
    return {"target_changed": target_changed,
            "missing": missing,
            "complete": complete or not target_changed,
            "rule": "target 变化必须同时解释 WHAT/WHY/BINDING"}
