# coding: utf-8
"""Production Autonomy Governor（QCFP-MTF 2.8：100 号生产自治治理器）

明确哪些事情系统可以自动做、哪些必须禁止：
    LEVEL 0 READ ONLY / LEVEL 1 ANALYSIS / LEVEL 2 RECOMMENDATION /
    LEVEL 3 CONTROLLED EXECUTION

核心原则：系统可以自动执行被授权的动作，但不能自动扩大自己的权限
（不能修改 Permission/Risk/Model/PIT、绕过 OOS/Ablation、自行批准新版本）。
"""

from dataclasses import asdict, dataclass, field


AUTONOMY_LEVELS = ("READ_ONLY", "ANALYSIS", "RECOMMENDATION",
                   "CONTROLLED_EXECUTION")

# 行为 → 所需最低自治级别（FORBIDDEN = 任何级别都禁止）
AUTONOMY_MATRIX = {
    "compute_wave": "ANALYSIS",
    "generate_signal": "ANALYSIS",
    "generate_recommendation": "RECOMMENDATION",
    "auto_reduce_position": "CONTROLLED_EXECUTION",
    "trigger_hard_risk_exit": "CONTROLLED_EXECUTION",
    "auto_enter_position": "FORBIDDEN",       # 自动建仓需人工/受控审批
    "modify_permission_rule": "FORBIDDEN",
    "modify_risk_cap": "FORBIDDEN",
    "modify_production_model": "FORBIDDEN",
    "modify_pit_definition": "FORBIDDEN",
    "bypass_oos": "FORBIDDEN",
    "bypass_ablation": "FORBIDDEN",
    "self_approve_new_version": "FORBIDDEN",
}


@dataclass(frozen=True)
class AutonomyDecision:
    action: str
    level: str
    allowed: bool
    reason: str

    def as_dict(self) -> dict:
        return asdict(self)


def _level_index(level) -> int:
    return AUTONOMY_LEVELS.index(level) if level in AUTONOMY_LEVELS else -1


def autonomy_gate(action, current_level="READ_ONLY") -> AutonomyDecision:
    """自治门：行为所需级别 ≤ 当前级别才允许；FORBIDDEN 永远禁止。"""
    required = AUTONOMY_MATRIX.get(action)
    if required is None:
        return AutonomyDecision(action, current_level, True,
                                "UNKNOWN_ACTION_DEFAULT_ALLOW")
    if required == "FORBIDDEN":
        return AutonomyDecision(action, current_level, False,
                                f"{action} 永远禁止自动执行")
    if _level_index(required) <= _level_index(current_level):
        return AutonomyDecision(action, current_level, True,
                                f"{action} 需 {required}，当前 {current_level}")
    return AutonomyDecision(action, current_level, False,
                            f"{action} 需 {required}，当前 {current_level} 不足")


def autonomy_report(level="READ_ONLY") -> dict:
    """当前自治级别下允许/禁止的行为清单。"""
    allowed = []
    forbidden = []
    for action, required in AUTONOMY_MATRIX.items():
        g = autonomy_gate(action, level)
        (allowed if g.allowed else forbidden).append(action)
    return {"level": level, "allowed": allowed, "forbidden": forbidden}
