# coding: utf-8
"""Institutional Permission Engine（正式接口，QCFP-MTF 2.2）

Institutional Permission 是交易上限（RULE 01），只能被上层风险降级，
不能被 Daily 信号升级（RULE 02）。
"""

from dataclasses import dataclass, field

from .state_engine import institutional_state
from .pressure import institutional_pressure

PERMISSION_LEVELS = {"BLOCK": 0, "WATCH": 1, "TEST": 2, "ALLOW": 3, "STRONG_ALLOW": 4}


@dataclass(frozen=True)
class InstitutionalPermission:
    state: str
    permission: str
    pressure: int
    persistence: int
    confidence: str
    reasons: tuple = field(default_factory=tuple)
    downgraded: bool = False

    def as_dict(self) -> dict:
        return {"state": self.state, "permission": self.permission,
                "pressure": self.pressure, "persistence": self.persistence,
                "confidence": self.confidence, "reason_codes": list(self.reasons),
                "downgraded": self.downgraded}


def _base_permission(state, pressure, persistence) -> str:
    if state == "ACCUMULATION":
        if pressure >= 2 and persistence >= 2:
            return "STRONG_ALLOW"
        if pressure >= 1 and persistence >= 2:
            return "ALLOW"
        return "WATCH"
    if state == "ACCUMULATION_WEAK":
        return "WATCH"
    if state == "NEUTRAL":
        return "WATCH"
    if state == "RECOVERY":
        return "TEST" if pressure >= 1 and persistence >= 1 else "WATCH"
    if state == "DISTRIBUTION":
        return "BLOCK" if pressure <= -1 and persistence >= 2 else "WATCH"
    if state == "DISTRIBUTION_STRONG":
        return "BLOCK" if pressure <= -2 and persistence >= 2 else "WATCH"
    if state == "CAPITULATION":
        return "BLOCK"
    return "WATCH"


def evaluate_institutional_permission(
        institutional_state_name=None, pressure=None, persistence=0,
        divergence=False, confidence="Medium", data_quality="B",
        market_risk=False, c_state=None, f_state=None, p_state=None,
        settings=None) -> InstitutionalPermission:
    """正式权限评估（返回 InstitutionalPermission 冻结对象）"""
    if institutional_state_name is None:
        institutional_state_name = institutional_state(c_state, f_state, p_state)
    if pressure is None:
        pressure = institutional_pressure(c_state, f_state)
    permission = _base_permission(institutional_state_name, pressure, int(persistence))
    reasons = []
    downgraded = False

    def _downgrade(target, reason):
        nonlocal permission, downgraded
        if PERMISSION_LEVELS[target] < PERMISSION_LEVELS[permission]:
            permission = target
            downgraded = True
            reasons.append(reason)

    if divergence:
        _downgrade("WATCH", "divergence")
    if confidence == "Low":
        _downgrade("WATCH", "low_confidence")
    if data_quality == "D":
        _downgrade("BLOCK", "poor_data_quality")
    if market_risk:
        _downgrade("TEST", "market_risk_off")
    return InstitutionalPermission(
        state=institutional_state_name, permission=permission,
        pressure=int(pressure), persistence=int(persistence),
        confidence=confidence, reasons=tuple(reasons), downgraded=downgraded)
