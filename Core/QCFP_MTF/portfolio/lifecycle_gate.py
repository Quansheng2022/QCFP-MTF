# coding: utf-8
"""Portfolio Lifecycle Gate（QCFP-MTF 2.8：21 号组合状态作用于持仓全生命周期）

Portfolio State 不只限制"新仓"，而是对整个持仓生命周期起作用：
    ENTRY / ADD / HOLD / REDUCE / EXIT 每个动作都要过组合状态门。

动作门规则（按状态）：
    NORMAL        全开
    DEFENSIVE     ENTRY/ADD 需确认，EntryCap×0.7
    RISK_OFF      禁 ENTRY/ADD，优先 REDUCE
    CONCENTRATED  ENTRY 降额，ADD 需分散检查，优先 REDUCE
    OVERHEATED    禁 ENTRY/ADD，允许 HOLD/REDUCE/EXIT
    RECOVERY      全开（恢复期）

约束：本门只做"组合级"限制，不改变 Permission / FSM / Risk 单股约束；
单股硬门（Hard Exit / BLOCK）优先级更高，且本门结果可被上游直接否决。
"""

from dataclasses import asdict, dataclass, field


ACTIONS = ("ENTRY", "ADD", "HOLD", "REDUCE", "EXIT")


@dataclass(frozen=True)
class PortfolioGateDecision:
    state: str
    action: str
    allowed: bool
    cap_scale: float
    reason: str
    reasons: tuple = field(default_factory=tuple)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["reasons"] = list(self.reasons)
        return d


# 状态 × 动作 门（默认 allowed；False = 该动作被组合状态禁止）
ACTION_GATE_MATRIX = {
    "NORMAL": {"ENTRY": True, "ADD": True, "HOLD": True,
               "REDUCE": True, "EXIT": True},
    "DEFENSIVE": {"ENTRY": True, "ADD": True, "HOLD": True,
                  "REDUCE": True, "EXIT": True},
    "RISK_OFF": {"ENTRY": False, "ADD": False, "HOLD": True,
                 "REDUCE": True, "EXIT": True},
    "CONCENTRATED": {"ENTRY": True, "ADD": True, "HOLD": True,
                     "REDUCE": True, "EXIT": True},
    "OVERHEATED": {"ENTRY": False, "ADD": False, "HOLD": True,
                   "REDUCE": True, "EXIT": True},
    "RECOVERY": {"ENTRY": True, "ADD": True, "HOLD": True,
                 "REDUCE": True, "EXIT": True},
}


def portfolio_action_gate(state, action, cap_scale_input=None,
                          concentration_add_ok=True,
                          require_confirmation=True) -> PortfolioGateDecision:
    """组合状态动作门。

    参数：
        state                  组合状态
        action                 ENTRY/ADD/HOLD/REDUCE/EXIT
        cap_scale_input        外部传入的 EntryCap 缩放（None = 按状态默认）
        concentration_add_ok   CONCENTRATED 状态下 ADD 是否满足分散检查
        require_confirmation   DEFENSIVE 下是否已获得确认
    """
    from .state_engine import state_constraints
    c = state_constraints(state)
    base_allowed = ACTION_GATE_MATRIX.get(state, ACTION_GATE_MATRIX["NORMAL"])
    reasons = []
    allowed = bool(base_allowed.get(action, True))
    cap_scale = float(cap_scale_input if cap_scale_input is not None
                      else c.get("entry_cap_scale", 1.0))
    if action in ("ENTRY", "ADD") and not allowed:
        reasons.append(f"{state}_BLOCKS_{action}")
    if action == "ENTRY" and state == "DEFENSIVE" \
            and require_confirmation:
        reasons.append("DEFENSIVE_REQUIRES_CONFIRMATION")
    if action == "ADD" and state == "CONCENTRATED":
        if not concentration_add_ok:
            allowed = False
            reasons.append("CONCENTRATED_ADD_NEEDS_DIVERSIFICATION")
        else:
            reasons.append("CONCENTRATED_ADD_DIVERSIFIED_OK")
    if action in ("REDUCE", "EXIT") and state in (
            "RISK_OFF", "CONCENTRATED", "OVERHEATED"):
        reasons.append(f"{state}_PRIORITIZES_{action}")
    if action in ("ENTRY", "ADD") and state == "RECOVERY":
        reasons.append("RECOVERY_ALLOWS_NEW_RISK")
    if action in ("ENTRY", "ADD") and not reasons and allowed:
        reasons.append(f"{state}_ALLOWS_{action}")
    if action in ("HOLD",) and allowed and not reasons:
        reasons.append(f"{state}_ALLOWS_HOLD")
    return PortfolioGateDecision(
        state=state, action=action, allowed=allowed,
        cap_scale=round(cap_scale, 4),
        reason="; ".join(reasons) if reasons else f"{state}_{action}_OK",
        reasons=tuple(reasons))


def apply_lifecycle_gate(state, target, previous_position, action,
                         cap_scale_input=None, **kw) -> dict:
    """把动作门应用到目标仓位（返回新 target 与门结果）。"""
    gate = portfolio_action_gate(
        state, action, cap_scale_input=cap_scale_input, **kw)
    t = float(target or 0.0)
    prev = float(previous_position or 0.0)
    if action in ("ENTRY", "ADD") and not gate.allowed:
        t = min(t, prev)          # 禁新增 → 不高于既有仓位
    elif action == "ENTRY":
        t = t * gate.cap_scale    # EntryCap 缩放
    elif action in ("REDUCE", "EXIT"):
        t = min(t, prev)          # 减仓/清仓只降不升
    return {"target": round(t, 4), "previous_position": round(prev, 4),
            "gate": gate.as_dict()}
