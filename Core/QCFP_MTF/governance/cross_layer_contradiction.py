# coding: utf-8
"""Cross-Layer Contradiction Audit（QCFP-MTF 2.8：87 号跨层矛盾审计）

不同层可以意见不同，但必须：
    1) 不越权；
    2) 能解释；
    3) 最终只有一个 Canonical Decision。

例如 Permission=BLOCK + Wave=ACTIVE + FSM=ADD + FinalTarget=0
完全合理，但必须表达为
"Opportunity detected but participation denied"，
而不是让用户看到互相矛盾的 BUY/NO BUY 文案。

允许的跨层关系：
    Opportunity != Permission / Proposal != Decision /
    Decision != Execution / Outcome != Decision Quality
"""


def cross_layer_contradiction_audit(evidence: dict) -> dict:
    """evidence：{institutional_permission, wave_state, fsm_action,
    final_target, proposal_action?}"""
    perm = evidence.get("institutional_permission")
    wave = evidence.get("wave_state")
    fsm = evidence.get("fsm_action")
    target = float(evidence.get("final_target") or 0.0)
    issues, explained = [], []
    if perm == "BLOCK" and target > 1e-9:
        issues.append({"type": "AUTHORITY_VIOLATION",
                       "detail": "BLOCK 下 FinalTarget 必须为 0（越权）"})
    if perm in ("BLOCK", "WATCH") and wave in ("ACTIVE", "CONFIRMING") \
            and target == 0:
        explained.append("Opportunity detected but participation denied")
    if fsm == "ADD" and target == 0 and perm in ("BLOCK", "WATCH"):
        explained.append("FSM 提案被权限层否决（Proposal != Decision）")
    proposal = evidence.get("proposal_action")
    if proposal and fsm and proposal != fsm:
        explained.append(
            f"Proposal({proposal}) 经 Governance 变为 Decision({fsm})")
    if issues:
        verdict = "VIOLATION"
    elif explained:
        verdict = "EXPLAINED"
    else:
        verdict = "CONSISTENT"
    return {"issues": issues, "explained": explained,
            "verdict": verdict,
            "single_canonical_decision": True,
            "rule": "不同层可意见不同，但必须不越权、能解释、"
                    "只有一个 Canonical Decision"}


SEMANTIC_BOUNDARIES = (
    ("Opportunity", "Permission"),
    ("Proposal", "Decision"),
    ("Decision", "Execution"),
    ("Outcome", "Decision Quality"),
)


def semantic_boundaries() -> dict:
    """新 87 号：固化四个语义边界。"""
    return {"boundaries": [f"{a} ≠ {b}" for a, b in SEMANTIC_BOUNDARIES],
            "rule": "不同层可以意见不同，但 final authority 永远只有一个"}


def authority_boundary_violation(evidence: dict) -> dict:
    """新 87 号：真正该报警的是——下游反向提高 Permission /
    Report 改写 Action / Execution 绕过 FinalTarget。"""
    violations = []
    if evidence.get("downstream_upgraded_permission"):
        violations.append("DOWNSTREAM_UPGRADED_PERMISSION")
    if evidence.get("report_rewrote_action"):
        violations.append("REPORT_REWROTE_ACTION")
    if evidence.get("execution_bypassed_final_target"):
        violations.append("EXECUTION_BYPASSED_FINAL_TARGET")
    return {"violations": violations,
            "verdict": "BOUNDARY_OK" if not violations
            else "BOUNDARY_VIOLATION",
            "rule": "跨层 disagreement 必须可解释，"
                    "但 final authority 永远只有一个"}
