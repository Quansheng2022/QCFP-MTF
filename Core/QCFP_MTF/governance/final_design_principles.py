# coding: utf-8
"""QCFP-MTF Final Design Principle（QCFP-MTF 2.8：100 号最终设计原则）

冻结未来所有版本的最高过滤器（十条）：
    1. Permission > Signal
    2. PIT > Prediction
    3. Risk > Return
    4. Proposal ≠ Decision
    5. Final risk can only decrease downstream
    6. UNKNOWN must degrade
    7. Production cannot self-modify
    8. Every decision must be auditable and replayable
    9. Research may challenge Production, never silently change it
    10. Complexity must prove incremental practical value

任何新 Feature Proposal 必须填写：
    Problem being solved / Existing module insufficiency /
    Expected incremental value / Complexity cost / OOS test /
    Ablation plan / Retirement condition
缺任何一个 → RESEARCH ONLY，不得进入 Production。
"""


FINAL_DESIGN_PRINCIPLES = (
    "Permission > Signal",
    "PIT > Prediction",
    "Risk > Return",
    "Proposal ≠ Decision",
    "Final risk can only decrease downstream",
    "UNKNOWN must degrade",
    "Production cannot self-modify",
    "Every decision must be auditable and replayable",
    "Research may challenge Production, never silently change it",
    "Complexity must prove incremental practical value",
)

FEATURE_PROPOSAL_FIELDS = (
    "problem_solved", "existing_module_insufficiency",
    "expected_incremental_value", "complexity_cost", "oos_test",
    "ablation_plan", "retirement_condition",
)


def feature_proposal_check(proposal: dict) -> dict:
    """缺任一字段 → RESEARCH ONLY，不得进入 Production。"""
    missing = [f for f in FEATURE_PROPOSAL_FIELDS
               if not proposal.get(f)]
    return {
        "missing_fields": missing,
        "verdict": "RESEARCH_ONLY" if missing else "PROPOSAL_ACCEPTED",
        "production_allowed": not missing,
        "rule": "缺任一字段 → RESEARCH ONLY",
    }


def design_principle_check(checks: dict) -> dict:
    """checks：{principle_index: bool} 或 {principle_text: bool}。"""
    failures = []
    for i, principle in enumerate(FINAL_DESIGN_PRINCIPLES, start=1):
        ok = checks.get(i) or checks.get(principle)
        if not ok:
            failures.append(principle)
    return {"failures": failures,
            "pass": not failures,
            "verdict": "CONFORMANT" if not failures
            else "PRINCIPLE_VIOLATION",
            "rule": "未来所有修改先经过这十条原则"}


def final_design_principle_gate(checks: dict,
                                performance_evidence: dict = None) -> dict:
    """新 100 号：FinalDesignPrincipleCheck = CONFORMANT，否则
    PROMOTION REJECTED——无论收益改善多少。这是 1–100 的停止规则。"""
    r = design_principle_check(checks)
    if r["verdict"] != "CONFORMANT":
        return {"verdict": "PROMOTION_REJECTED",
                "failures": r["failures"],
                "performance_evidence": performance_evidence,
                "allowed": False,
                "stop_rule": True,
                "rule": "未来所有 Release 必须 FinalDesignPrincipleCheck "
                        "= CONFORMANT，否则拒绝 Promotion，"
                        "无论收益改善多少"}
    return {"verdict": "PROMOTION_OK",
            "failures": [],
            "performance_evidence": performance_evidence,
            "allowed": True,
            "stop_rule": True}
