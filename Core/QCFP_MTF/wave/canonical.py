# coding: utf-8
"""Wave Stage → Canonical Proposal Chain（QCFP-MTF 2.8：P0-8 号）

生产只保留 DISCOVERY→CONFIRMING→ACTIVE→MATURE→EXHAUSTING→INVALID
（天然对应交易行为），并真正放入 Canonical 提案链：
    Wave Stage → allowed action → max_entry_scale → FSM proposal →
    FinalTarget（全部进入 DecisionSnapshot 与 Ledger）

Q4（Complexity Closure）：wave.stage_gate 已 MERGE 进本模块——
Wave Authority 唯一 Owner = wave.canonical；stage_gate.py 已物理删除。
"""

from ..decision.permission_policy import permission_policy_object


STAGE_ACTION_MATRIX = {
    "DISCOVERY": {"entry": False, "add": False, "hold": True,
                  "reduce": False, "max_entry_scale": 0.0},
    "CONFIRMING": {"entry": True, "add": False, "hold": True,
                   "reduce": False, "max_entry_scale": 0.5},
    "ACTIVE": {"entry": True, "add": True, "hold": True,
               "reduce": False, "max_entry_scale": 1.0},
    "MATURE": {"entry": True, "add": False, "hold": True,
               "reduce": False, "max_entry_scale": 0.5},
    "EXHAUSTING": {"entry": False, "add": False, "hold": True,
                   "reduce": True, "max_entry_scale": 0.0},
    "INVALID": {"entry": False, "add": False, "hold": False,
                "reduce": True, "max_entry_scale": 0.0},
}

# Convergence 新 9B 号：Production Wave Taxonomy 唯一——
# wave_stage 只允许 6 个生命周期状态；诊断阶段另名 wave_phase_diagnostic
PRODUCTION_WAVE_TAXONOMY = (
    "DISCOVERY", "CONFIRMING", "ACTIVE", "MATURE", "EXHAUSTING", "INVALID")

DIAGNOSTIC_WAVE_PHASES = (
    "FORMATION", "TRIGGER", "EXPANSION", "ACCELERATION",
    "DISTRIBUTION", "DECAY")


def wave_taxonomy_split(stage: str) -> dict:
    """新 9B 号：wave_stage = Production Lifecycle；
    诊断阶段 → wave_phase_diagnostic（RESEARCH_ONLY，不能进入 Governance）。"""
    s = str(stage or "").upper()
    if s in PRODUCTION_WAVE_TAXONOMY:
        return {"stage": s, "kind": "wave_stage",
                "production_governance": True}
    if s in DIAGNOSTIC_WAVE_PHASES:
        return {"stage": s, "kind": "wave_phase_diagnostic",
                "production_governance": False,
                "verdict": "RESEARCH_ONLY_DIAGNOSTIC"}
    return {"stage": s, "kind": "UNKNOWN",
            "production_governance": False}


def production_wave_taxonomy_check(uses: dict) -> dict:
    """新 9B 号：Production Wave Taxonomy = 1——
    正式 Governance 只消费 wave_stage（6 态），诊断阶段不得进入。"""
    violations = []
    for module, stage in (uses or {}).items():
        split = wave_taxonomy_split(stage)
        if split["kind"] == "wave_phase_diagnostic":
            violations.append({"module": module, "stage": stage})
    return {"violations": violations,
            "production_wave_taxonomy_count": 1,
            "verdict": "SINGLE_TAXONOMY" if not violations
            else "DUPLICATE_TAXONOMY",
            "rule": "wave_stage 只允许 DISCOVERY→CONFIRMING→ACTIVE→"
                    "MATURE→EXHAUSTING→INVALID；诊断阶段只能 "
                    "RESEARCH_ONLY/DIAGNOSTIC"}


def wave_stage_gate(stage, action, max_entry_scale_input=None) -> dict:
    """Wave 阶段门：返回 {allowed, max_entry_scale, reason}。"""
    s = str(stage or "").upper()
    rules = STAGE_ACTION_MATRIX.get(s, STAGE_ACTION_MATRIX["DISCOVERY"])
    action = str(action or "").upper()
    key = "entry" if action in ("ENTRY", "ADD") and action == "ENTRY" \
        else "add" if action == "ADD" else "hold" if action == "HOLD" \
        else "reduce" if action in ("REDUCE", "EXIT") else None
    if key is None:
        return {"allowed": True, "max_entry_scale": 1.0,
                "reason": f"UNKNOWN_ACTION({action})"}
    allowed = bool(rules.get(key, True))
    scale = float(max_entry_scale_input
                  if max_entry_scale_input is not None
                  else rules.get("max_entry_scale", 1.0))
    if action == "ADD":
        allowed = bool(rules.get("add", False))
    reason = f"{s}_{action}_{'ALLOWED' if allowed else 'BLOCKED'}"
    return {"allowed": allowed, "max_entry_scale": scale, "reason": reason}


def apply_wave_stage_to_target(stage, target, previous_position,
                               action="ENTRY") -> dict:
    """把阶段门应用到目标仓位。"""
    g = wave_stage_gate(stage, action)
    t = float(target or 0.0)
    prev = float(previous_position or 0.0)
    if action in ("ENTRY", "ADD") and not g["allowed"]:
        t = min(t, prev)
    elif action == "ENTRY":
        t = t * g["max_entry_scale"]
    return {"target": round(t, 4), "previous_position": round(prev, 4),
            "gate": g}


def wave_to_canonical(stage, permission, raw_target, previous_position=0.0,
                      proposed_action="ENTRY") -> dict:
    """Wave 阶段 → 权限 → 动作 → 最大进场比例 → 提案目标。

    返回 {stage, action, allowed, max_entry_scale, proposed_target,
    permission_policy, blocked_reason}。
    """
    gate = wave_stage_gate(stage, proposed_action)
    pol = permission_policy_object(permission)
    t = float(raw_target or 0.0)
    prev = float(previous_position or 0.0)
    reasons = []
    if not gate["allowed"]:
        reasons.append(f"WAVE_STAGE_{stage}_BLOCKS_{proposed_action}")
    if not pol["new_risk_allowed"] and proposed_action in ("ENTRY", "ADD"):
        reasons.append(f"PERMISSION_{permission}_BLOCKS_NEW_RISK")
    if reasons:
        return {"stage": stage, "action": proposed_action,
                "allowed": False, "max_entry_scale": gate["max_entry_scale"],
                "proposed_target": round(min(t, prev), 4),
                "permission_policy": pol,
                "blocked_reason": "; ".join(reasons)}
    scaled = t * gate["max_entry_scale"]
    capped = min(scaled, pol["max_target"])
    return {"stage": stage, "action": proposed_action,
            "allowed": True, "max_entry_scale": gate["max_entry_scale"],
            "proposed_target": round(capped, 4),
            "permission_policy": pol,
            "blocked_reason": ""}
