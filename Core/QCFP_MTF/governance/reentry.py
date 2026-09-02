# coding: utf-8
"""Re-entry / Cooldown 治理（QCFP-MTF 2.7：降低 Whipsaw）

EXIT → COOLDOWN → RE-ENTRY 严格规则：
    记录 last_exit_date / exit_reason / cooldown_days / reentry_trigger /
    reentry_wave_id；只有冷却结束 + 机构再确认 + Setup 再确认 + Risk 允许
    + Permission>=WATCH 才能重新进入 TESTING。
"""

from dataclasses import asdict, dataclass

import pandas as pd

from .feature_gate import feature_allowed  # noqa: F401（复用信息层门）


@dataclass(frozen=True)
class ReentryState:
    last_exit_date: str = ""
    exit_reason: str = ""
    cooldown_days: int = 14
    reentry_trigger: str = ""
    reentry_wave_id: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def reentry_allowed(state: ReentryState, decision_date, institutional_state,
                    setup_type, risk_level, permission,
                    cooldown_days=None) -> tuple:
    """返回 (allowed, reasons)；需要 wave_id 再确认时传入 reentry_wave_id"""
    from ..decision.permission_policy import permission_level
    reasons = []
    cd = cooldown_days or state.cooldown_days
    if state.last_exit_date:
        elapsed = int((pd.Timestamp(decision_date)
                       - pd.Timestamp(state.last_exit_date)).days)
        if elapsed < cd:
            reasons.append(f"COOLDOWN_ACTIVE({elapsed}/{cd}d)")
    if institutional_state in (None, "", "DISTRIBUTION",
                               "DISTRIBUTION_STRONG", "CAPITULATION"):
        reasons.append("INSTITUTIONAL_NOT_CONFIRMED")
    if setup_type in (None, "NONE"):
        reasons.append("SETUP_ABSENT")
    if risk_level not in ("Low", "Medium"):
        reasons.append("RISK_TOO_HIGH")
    if permission_level(permission) < permission_level("WATCH"):
        reasons.append("PERMISSION_BELOW_WATCH")
    return not reasons, tuple(reasons)


def record_exit(prev_state, exit_reason="", decision_date="",
                cooldown_days=14) -> ReentryState:
    """EXITING 完成后登记 ReentryState（供后续再入场校验）"""
    return ReentryState(last_exit_date=decision_date or "",
                        exit_reason=exit_reason or "",
                        cooldown_days=cooldown_days)
