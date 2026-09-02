# coding: utf-8
"""Regime Transition State Machine（QCFP-MTF 2.8：86 号市场状态转换 FSM）

显式市场状态机（双向）：
    BULL_STABLE → BULL_WEAKENING → TRANSITION → BEAR_CONFIRMING →
    BEAR_STABLE（反向：BEAR_STABLE → RECOVERY → TRANSITION →
    BULL_CONFIRMING → BULL_STABLE）

每个 Transition 定义 Permission / Wave / Risk / Position 效果：
    例如 BULL_WEAKENING：Permission Cap ↓ / Position Cap ↓ / Entry ↑
    （不一定立即 BLOCK，但主动降风险）。
"""

from dataclasses import asdict, dataclass, field


REGIME_FSM_STATES = (
    "BULL_STABLE", "BULL_WEAKENING", "TRANSITION", "BEAR_CONFIRMING",
    "BEAR_STABLE", "RECOVERY", "BULL_CONFIRMING",
)


@dataclass(frozen=True)
class RegimeTransition:
    from_state: str
    to_state: str
    permission_effect: float    # 1.0 = 不变，<1 = 权限收紧
    wave_effect: float
    risk_effect: float
    position_effect: float
    entry_threshold_up: float
    reasons: tuple = field(default_factory=tuple)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["reasons"] = list(self.reasons)
        return d


# 状态转移表：{from: {to: (perm, wave, risk, pos, entry_up)}}
TRANSITIONS = {
    "BULL_STABLE": {"BULL_WEAKENING": (0.9, 0.9, 1.1, 0.9, 1.05)},
    "BULL_WEAKENING": {"TRANSITION": (0.7, 0.8, 1.2, 0.7, 1.1)},
    "TRANSITION": {"BEAR_CONFIRMING": (0.5, 0.6, 1.3, 0.5, 1.2),
                   "BULL_CONFIRMING": (0.8, 0.9, 1.0, 0.8, 1.05)},
    "BEAR_CONFIRMING": {"BEAR_STABLE": (0.3, 0.4, 1.4, 0.3, 1.3)},
    "BEAR_STABLE": {"RECOVERY": (0.6, 0.7, 1.0, 0.6, 1.1)},
    "RECOVERY": {"TRANSITION": (0.8, 0.9, 0.9, 0.8, 1.0)},
    "BULL_CONFIRMING": {"BULL_STABLE": (1.0, 1.0, 1.0, 1.0, 1.0)},
}


def regime_transition(current_state, target_state) -> RegimeTransition:
    """状态转移（显式治理）。"""
    spec = TRANSITIONS.get(current_state, {}).get(target_state)
    if spec is None:
        raise ValueError(
            f"RegimeFSM: 非法转移 {current_state}→{target_state}"
            f"（必须经 TRANSITION）")
    perm, wave, risk, pos, entry = spec
    return RegimeTransition(
        from_state=current_state, to_state=target_state,
        permission_effect=perm, wave_effect=wave, risk_effect=risk,
        position_effect=pos, entry_threshold_up=entry,
        reasons=(f"{current_state}→{target_state}",))


def apply_regime_transition(target, transition: RegimeTransition,
                            previous_position=0.0) -> dict:
    """把状态转移效果作用到目标仓位。"""
    t = float(target or 0.0)
    prev = float(previous_position or 0.0)
    t = t * transition.position_effect * transition.permission_effect
    return {"target": round(t, 4),
            "permission_scale": transition.permission_effect,
            "position_scale": transition.position_effect,
            "entry_threshold_up": transition.entry_threshold_up,
            "previous_position": round(prev, 4)}
