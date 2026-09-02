# coding: utf-8
"""Sunset Policy（QCFP-MTF 2.8：95 号模块/策略日落策略）

正式到期机制：
    ACTIVE → REVIEW_DUE → SUNSET_CANDIDATE → SHADOW_ONLY → RETIRED
触发条件：
    Evidence expired / No incremental value / Never binding /
    Dominated / Repeated OOS failure / Excessive complexity

验收标准：模块不会因为"没人敢删"而永久留在 Production。
默认不是永久 ACTIVE，而是必须持续证明自己值得 ACTIVE。
"""


SUNSET_LIFECYCLE = ("ACTIVE", "REVIEW_DUE", "SUNSET_CANDIDATE",
                    "SHADOW_ONLY", "RETIRED")

SUNSET_TRIGGERS = ("evidence_expired", "no_incremental_value",
                   "never_binding", "dominated", "repeated_oos_failure",
                   "excessive_complexity")

_ORDER = {s: i for i, s in enumerate(SUNSET_LIFECYCLE)}


def sunset_policy(module, triggers, current_state="ACTIVE") -> dict:
    """按触发条件推进日落生命周期（只进不退）。"""
    triggers = [t for t in (triggers or []) if t in SUNSET_TRIGGERS]
    n = len(triggers)
    if not triggers:
        target = "ACTIVE"
    elif n == 1:
        target = "REVIEW_DUE"
    else:
        target = "SUNSET_CANDIDATE"
    if "repeated_oos_failure" in triggers or "evidence_expired" in triggers:
        target = "SHADOW_ONLY" if n >= 2 else target
    if _ORDER[target] < _ORDER.get(current_state, 0):
        target = current_state  # 只进不退
    return {"module": module, "triggers": triggers,
            "state": target,
            "rule": "默认不是永久 ACTIVE，"
                    "必须持续证明自己值得 ACTIVE"}


def advance_sunset(current, target) -> str:
    if current not in SUNSET_LIFECYCLE or target not in SUNSET_LIFECYCLE:
        raise ValueError(f"非法日落状态 {current}→{target}")
    if _ORDER[target] < _ORDER[current]:
        raise ValueError(f"禁止回退日落状态 {current}→{target}")
    return target


def retirement_condition_required(feature, retirement_condition) -> dict:
    """新 95 号：所有 ACTIVE 模块必须有 retirement_condition；
    没有 → 不得进入 Production。"""
    if not str(retirement_condition or "").strip():
        return {"feature": feature,
                "production_allowed": False,
                "verdict": "PRODUCTION_BLOCKED",
                "reason": "没有 Retirement Condition 不得进入 Production"}
    return {"feature": feature,
            "production_allowed": True,
            "verdict": "RETIREMENT_CONDITION_PRESENT"}


def feature_sunset_eligibility(feature, conditions: list) -> dict:
    """新 95 号：ACTIVE Feature 是"暂时获得继续存在资格"，
    命中触发条件 → 进入 Sunset。"""
    active_triggers = [c for c in (conditions or [])
                       if c in SUNSET_TRIGGERS]
    if active_triggers:
        return {"feature": feature,
                "verdict": "ENTER_SUNSET",
                "triggers": active_triggers}
    return {"feature": feature,
            "verdict": "ACTIVE_CONTINUES",
            "triggers": []}
