# coding: utf-8
"""Human Override Contract（QCFP-MTF 2.8：61 号人工干预契约）

人工干预不是 Ledger 外的黑箱，而是正式事件：
    OVERRIDE_SKIP / OVERRIDE_REDUCE / OVERRIDE_EXIT / OVERRIDE_HALT
每次记录：原 Canonical Decision、人工动作、reason code、时间、操作者、
最终执行结果。

原则：
    - 允许人工负责，但不允许人工无痕；
    - 人工默认只能降低风险，不能突破 Canonical 的风险上限；
    - 任何 executed_position != canonical_target 都必须能解释原因。
"""


OVERRIDE_TYPES = ("OVERRIDE_SKIP", "OVERRIDE_REDUCE",
                  "OVERRIDE_EXIT", "OVERRIDE_HALT")


def human_override_event(decision_id, canonical_target, override_type,
                         executed_position, operator, reason_code,
                         timestamp, authorized_escalation=False,
                         note="") -> dict:
    """生成正式人工干预事件记录。"""
    if override_type not in OVERRIDE_TYPES:
        raise ValueError(f"非法人工动作: {override_type}")
    canonical = float(canonical_target or 0.0)
    executed = float(executed_position or 0.0)
    escalation = executed > canonical + 1e-9 and \
        not authorized_escalation
    return {
        "decision_id": decision_id,
        "canonical_target": canonical,
        "executed_position": executed,
        "override_type": override_type,
        "operator": operator,
        "reason_code": reason_code,
        "timestamp": timestamp,
        "authorized_escalation": bool(authorized_escalation),
        "escalation_unauthorized": escalation,
        "explainable": True,
        "note": note,
        "rule": "允许人工负责，但不允许人工无痕；"
                "默认不得突破 Canonical 风险上限",
    }


def explain_divergence(canonical_target, executed_position,
                       override_events) -> dict:
    """任何 executed != canonical 都必须能被事件解释。"""
    canonical = float(canonical_target or 0.0)
    executed = float(executed_position or 0.0)
    diverged = abs(executed - canonical) > 1e-9
    events = list(override_events or [])
    if not diverged:
        return {"diverged": False, "explained": True,
                "reason": "执行仓位与 Canonical 一致"}
    if not events:
        return {"diverged": True, "explained": False,
                "reason": "执行仓位与 Canonical 不一致但无人工事件"
                          "（禁止无痕干预）"}
    return {"diverged": True, "explained": True,
            "reason": f"由 {len(events)} 条人工事件解释",
            "events": events}


ALLOWED_OVERRIDE_TYPES = ("OVERRIDE_SKIP", "OVERRIDE_REDUCE",
                          "OVERRIDE_EXIT", "OVERRIDE_HALT")


def override_permission_boundary(override_type, target,
                                 canonical_target) -> dict:
    """新 61 号：Human Override 默认只能 SKIP/REDUCE/EXIT/HALT；
    不能未经额外治理 ADD / 扩大仓位 / 突破 Permission / Risk Cap。"""
    t = float(target or 0.0)
    c = float(canonical_target or 0.0)
    if override_type not in ALLOWED_OVERRIDE_TYPES:
        return {"allowed": False,
                "reason": f"{override_type} 不在允许的人工动作内"}
    if t > c + 1e-9:
        return {"allowed": False,
                "reason": "人工不能私下获得比 Canonical 更大的风险权限"}
    return {"allowed": True,
            "reason": "人工只承担'少做'的责任，不扩大风险权限"}


def override_ledger_chain(canonical_target, override_action,
                          override_target, override_reason_code,
                          executed_target, operator) -> dict:
    """新 61 号：Canonical → Human Override → Executed 正式事实链。

    验收标准：ExecutedTarget != CanonicalTarget 必须存在 OverrideEvent，
    否则 Ledger Integrity FAIL。
    """
    import hashlib
    import json
    canonical = float(canonical_target or 0.0)
    executed = float(executed_target or 0.0)
    override_target = float(override_target or 0.0)
    diverged = abs(executed - canonical) > 1e-9
    override_event_id = hashlib.sha256(
        json.dumps({"canonical": canonical, "action": override_action,
                    "override_target": override_target,
                    "reason": override_reason_code,
                    "executed": executed, "operator": operator},
                   sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:16]
    integrity_ok = not diverged or bool(override_action)
    return {
        "canonical_target": canonical,
        "override_action": override_action,
        "override_target": override_target,
        "override_reason_code": override_reason_code,
        "executed_target": executed,
        "override_event_id": override_event_id,
        "operator": operator,
        "diverged": diverged,
        "ledger_integrity": "OK" if integrity_ok else "FAIL",
        "rule": "ExecutedTarget != CanonicalTarget 必须存在 OverrideEvent，"
                "否则 Ledger Integrity FAIL",
    }
