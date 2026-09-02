# coding: utf-8
"""Complexity Ceiling（QCFP-MTF 2.8：60 号复杂度硬上限）

从制度上停止无限扩张：给 Production 设置硬上限，而不是"建议不要太复杂"。
限制对象：ACTIVE decision modules / Canonical decision stages /
Decision-critical parameters / Independent scoring systems /
Duplicate authorities（不机械限制代码行数）。

规则：
    - 新模块进 Production 默认"一进一出"；
    - 净增 ≥3 个 ACTIVE 模块必须有强 OOS/Ablation/Stress 证据，
      否则拒绝 Promotion。
"""


COMPLEXITY_CEILING_LIMITS = {
    "active_decision_modules": 45,
    "canonical_decision_stages": 10,
    "decision_critical_parameters": 40,
    "independent_scoring_systems": 5,
    "duplicate_authorities": 0,
}


def complexity_ceiling_check(usage: dict, limits=None) -> dict:
    limits = limits or COMPLEXITY_CEILING_LIMITS
    consumption, over = [], []
    for key, limit in limits.items():
        used = int(usage.get(key) or 0)
        consumption.append({"dimension": key, "limit": limit,
                            "used": used, "over": used > limit})
        if used > limit:
            over.append(key)
    return {"consumption": consumption, "over_ceiling": over,
            "within_ceiling": not over,
            "verdict": "PROMOTE_OK" if not over else "REJECTED"}


def promotion_decision(proposed_modules, retired_modules=None,
                       evidence=None) -> dict:
    """一进一出 + 强证据要求。"""
    proposed = list(proposed_modules or [])
    retired = list(retired_modules or [])
    net = len(proposed) - len(retired)
    evidence = evidence or {}
    strong = bool(evidence.get("oos") and evidence.get("ablation")
                  and evidence.get("stress"))
    if net <= 0:
        verdict, reason = "ALLOW", "一进一出或净减法"
    elif net < 3:
        verdict, reason = ("ALLOW" if strong else "REVIEW",
                           "净增模块已有强证据"
                           if strong else "净增 <3 且证据不足 → 需 Review")
    else:
        verdict, reason = ("ALLOW" if strong else "REJECTED",
                           "净增 ≥3 且 OOS/Ablation/Stress 全通过"
                           if strong
                           else "净增 ≥3 且缺强证据 → 拒绝 Promotion")
    return {"proposed": proposed, "retired": retired,
            "net_added": net, "evidence_strong": strong,
            "verdict": verdict, "reason": reason,
            "one_in_one_out_default": True}


# 新 50 号：硬 Authority 目标（One-In/One-Out）
AUTHORITY_CEILING_TARGETS = {
    "canonical_decision_authority": 1,
    "permission_authority": 1,
    "final_target_authority": 1,
    "formal_validation_authority": 1,
    "production_wave_taxonomy": 1,
    "report_decision_authority": 0,
    "legacy_production_paths": 0,
}


def authority_ceiling_check(authorities: dict) -> dict:
    """新 50 号：Authority 数量硬上限检查。"""
    violations = []
    for key, limit in AUTHORITY_CEILING_TARGETS.items():
        actual = int(authorities.get(key) or 0)
        if actual > limit:
            violations.append({"authority": key, "limit": limit,
                               "actual": actual})
    return {"violations": violations,
            "within_ceiling": not violations,
            "verdict": "AUTHORITY_OK" if not violations
            else "AUTHORITY_OVER_CEILING",
            "rule": "Canonical/Permission/FinalTarget/Validation/Wave "
                    "Authority = 1；Report=0；Legacy Paths=0"}


def active_feature_gate(feature, evidence: dict) -> dict:
    """新 50 号：新增 Feature 想进 ACTIVE 必须证明六项，
    否则 RESEARCH_ONLY。"""
    required = ("existing_core_cannot_solve", "oos_incremental_value",
                "ablation_value", "stress_robustness",
                "retail_practicality", "complexity_cost_acceptable")
    missing = [k for k in required if not evidence.get(k)]
    return {
        "feature": feature,
        "missing_evidence": missing,
        "verdict": "RESEARCH_ONLY" if missing else "ACTIVE_ELIGIBLE",
        "production_allowed": not missing,
        "rule": "六项证据缺一不可，否则 RESEARCH_ONLY",
    }


def release_complexity_report(metrics: dict,
                              incremental_value_evidence: bool = False) -> dict:
    """新 50 号：大版本发布必须报告复杂度指标；复杂度上升必须附
    Incremental Value Evidence，否则不能 Promotion。"""
    complexity_rose = bool(metrics.get("complexity_rose"))
    if complexity_rose and not incremental_value_evidence:
        return {"verdict": "PROMOTION_REJECTED",
                "reason": "复杂度上升但缺 Incremental Value Evidence",
                "metrics": metrics,
                "allowed": False}
    return {"verdict": "PROMOTION_OK",
            "reason": "复杂度未上升或已附增量证据",
            "metrics": metrics,
            "allowed": True}


def complexity_promotion_veto(ceiling_check: dict,
                              incremental_value_evidence: bool = False) -> dict:
    """新 60 号：Complexity Ceiling 拥有否决 Promotion 的权力——
    超过 Ceiling 且没有足够 Incremental Value Evidence →
    PROMOTION_REJECTED。"""
    over = not ceiling_check.get("within_ceiling", True)
    if over and not incremental_value_evidence:
        return {"verdict": "PROMOTION_REJECTED",
                "reason": "超过 Complexity Ceiling 且缺 "
                          "Incremental Value Evidence",
                "allowed": False,
                "violations": ceiling_check.get("violations") or []}
    if over:
        return {"verdict": "PROMOTION_REVIEW",
                "reason": "超过 Ceiling 但已有增量证据 → 复审",
                "allowed": True}
    return {"verdict": "PROMOTION_OK",
            "reason": "复杂度在 Ceiling 内",
            "allowed": True}


def complexity_veto_release(ceiling_check: dict,
                            incremental_value_evidence=False,
                            minimal_retention=None) -> dict:
    """Release 3（新 30 号）：Complexity Ceiling 拥有最终 VETO——
    Complexity FAIL + 无强增量证据 → RELEASE REJECTED（不是 warning）。"""
    over = not ceiling_check.get("within_ceiling", True)
    if over and not incremental_value_evidence:
        return {"verdict": "RELEASE_REJECTED",
                "reason": "Complexity Ceiling FAIL + 无强增量证据 → "
                          "RELEASE REJECTED",
                "action": "SIMPLIFY",
                "allowed": False,
                "veto": True}
    if over and incremental_value_evidence:
        return {"verdict": "HUMAN_REVIEW",
                "reason": "超过 Ceiling 但有强证据 → Human Review",
                "action": "REVIEW",
                "allowed": True,
                "veto": False}
    return {"verdict": "RELEASE_OK",
            "reason": "复杂度在 Ceiling 内",
            "action": "KEEP",
            "allowed": True,
            "veto": False}
