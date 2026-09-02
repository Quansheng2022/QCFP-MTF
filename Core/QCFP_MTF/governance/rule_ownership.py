# coding: utf-8
"""Rule Ownership Registry（QCFP-MTF 2.8：72 号规则唯一拥有者）

每条关键业务规则只有一个权威拥有者：
    Permission upper bound → PermissionPolicy
    Final target → Governance
    Wave lifecycle → WaveStagePolicy
    Execution feasibility → Execution/Liquidity

验收标准：同一 rule_id 只能由一个 production module 决定，
其他模块只能读取或引用，不能复制实现。
"""


DEFAULT_RULE_OWNERS = {
    "permission_upper_bound": "PermissionPolicy",
    "final_target": "Governance",
    "wave_lifecycle": "WaveStagePolicy",
    "execution_feasibility": "ExecutionLiquidity",
}

# 新 72 号：决策关键规则的唯一 Owner（Architecture Conformance 核心依据）
CANONICAL_RULE_OWNERS = {
    "institution_to_permission": "PermissionPolicy",
    "permission_upper_bound": "PermissionPolicy",
    "wave_stage": "WaveStagePolicy",
    "fsm_transition": "RetailFSM",
    "hard_exit": "RiskExit",
    "final_target": "Governance",
    "tradability": "ExecutionTradability",
    "production_validation": "ValidationCertificate",
    "historical_fact": "Ledger",
}


def rule_ownership_check(declared_owners: dict) -> dict:
    """declared_owners：{rule_id: {"owner": module,
    "implementations": [modules]}}"""
    results, violations = {}, []
    for rule_id, info in (declared_owners or {}).items():
        owner = info.get("owner")
        implementations = list(info.get("implementations") or [])
        unique = set(implementations)
        duplicate = len(unique) > 1
        owner_present = owner in unique
        ok = (not duplicate) and owner_present
        results[rule_id] = {
            "owner": owner,
            "implementations": implementations,
            "duplicate_authority": duplicate,
            "owner_present": owner_present,
            "ok": ok,
        }
        if not ok:
            violations.append(rule_id)
    return {"results": results, "violations": violations,
            "single_owner": not violations,
            "rule": "同一 rule_id 只能由一个 production module 决定，"
                    "其余只能读取引用"}


def assert_single_owner(rule_id, owner, implementations) -> dict:
    unique = set(implementations or [])
    duplicate = len(unique) > 1
    return {
        "rule_id": rule_id,
        "owner": owner,
        "implementations": sorted(unique),
        "duplicate_authority": duplicate,
        "verdict": "DUPLICATE_AUTHORITY" if duplicate else "SINGLE_OWNER",
        "note": "重复实现属于架构违规，必须收敛到唯一 owner",
    }


def rule_owner_violation_check(rule_id, implementing_module) -> dict:
    """新 72 号：非 Owner 模块实现 decision-critical rule_id →
    RULE_OWNER_VIOLATION（只能 CONSUME，不能 REINTERPRET）。"""
    owner = CANONICAL_RULE_OWNERS.get(rule_id)
    if owner is None:
        return {"rule_id": rule_id, "known_rule": False,
                "violation": False}
    violation = str(implementing_module) != owner
    return {
        "rule_id": rule_id,
        "owner": owner,
        "implementing_module": implementing_module,
        "violation": violation,
        "verdict": "RULE_OWNER_VIOLATION" if violation
        else "OWNER_OK",
        "rule": "每个 decision-critical rule_id 的 Production Owner "
                "数量必须 = 1",
    }
