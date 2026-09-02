# coding: utf-8
"""Entry / Add / Reduce / Exit 四级动作模型（QCFP-MTF 2.8）

每个动作必须同时经过 Permission + Wave + FSM + Risk + Budget：
    ENTRY   权限≥TEST + Setup + Risk≤Medium + 空仓
    ADD     权限≥ALLOW + FSM∈{TESTING,BUILDING} + Risk≤Medium + 仓位<预算
    REDUCE  TRIMMING / Risk High / Permission 降级
    EXIT    Hard Exit / FSM=EXITING
    HOLD/WAIT 其余
"""


def evaluate_action(permission, fsm_state, setup_type, risk_level,
                    position, budget_cap, hard_exit=False,
                    entry_quality=None, wave_strength=0.0) -> tuple:
    """四级动作评估。

    2.8（14 号）：传入 EntryQuality 时，ENRTRY 前先过进场质量门——
    STRONG Wave + LOW Entry → WAIT（机会存在但介入点差）。
    entry_quality 为 None 时行为与 2.7 完全一致（默认兼容）。
    """
    reasons = []
    if hard_exit or fsm_state == "EXITING":
        return "EXIT", tuple(reasons)
    if fsm_state == "COOLDOWN":
        return "WAIT", ("COOLDOWN",)
    if fsm_state == "TRIMMING" or risk_level in ("High", "Extreme") \
            or permission == "BLOCK":
        return "REDUCE", tuple(reasons)
    if fsm_state == "HOLDING":
        return "HOLD", tuple(reasons)
    if fsm_state in ("TESTING", "BUILDING"):
        if permission in ("ALLOW", "STRONG_ALLOW") \
                and risk_level in ("Low", "Medium") \
                and float(position or 0.0) < float(budget_cap or 1.0) - 1e-9:
            # 2.8（14 号）：0 仓位 ADD 即"首次进场"，同样过进场质量门
            if float(position or 0.0) <= 1e-9 and entry_quality is not None:
                from .entry_quality import entry_quality_gate
                allowed, eq_reason = entry_quality_gate(
                    float(wave_strength or 0.0), entry_quality)
                if not allowed:
                    reasons.append(eq_reason)
                    return "WAIT", tuple(reasons)
            return "ADD", tuple(reasons)
        reasons.append("NO_ADD_QUALIFICATION")
        return "HOLD", tuple(reasons)
    # FLAT
    if permission in ("TEST", "ALLOW", "STRONG_ALLOW") \
            and setup_type not in (None, "NONE") \
            and risk_level in ("Low", "Medium"):
        if entry_quality is not None:
            from .entry_quality import entry_quality_gate
            allowed, eq_reason = entry_quality_gate(
                float(wave_strength or 0.0), entry_quality)
            if not allowed:
                reasons.append(eq_reason)
                return "WAIT", tuple(reasons)
        return "ENTRY", tuple(reasons)
    reasons.append("NO_ENTRY_QUALIFICATION")
    return "WAIT", tuple(reasons)
