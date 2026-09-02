# coding: utf-8
"""Execution Gate（QCFP-MTF 2.8：新 6 号执行资格门）

Execution Engine 只接受 CertifiedDecision：
    execute(CertifiedDecision) → 允许
    execute(DecisionSnapshot) → 拒绝（裸快照没有认证资格）

原则：不知道就降级，而且这个降级必须具有执行权。
"""


class ExecutionGateError(TypeError):
    pass


def assert_execution_eligible(decision) -> dict:
    """资格检查（无 side effect）：只有 CertifiedDecision 才可执行。

    PAPER 与 SMALL_LIVE 共用同一资格；不新增第二套 Certification
    Authority。裸 DecisionSnapshot → 拒绝。"""
    from ..decision.certified_decision import CertifiedDecision
    if isinstance(decision, CertifiedDecision):
        return {"eligible": True, "reasons": [],
                "decision_id": decision.decision_id,
                "certificate_id": decision.certificate_id}
    return {"eligible": False,
            "reasons": ["CERTIFIED_DECISION_REQUIRED"],
            "rule": "Execution 只接受 CertifiedDecision；"
                    "裸 DecisionSnapshot 没有认证资格"}


def execute(decision) -> dict:
    """唯一执行入口：只接受 CertifiedDecision。"""
    elig = assert_execution_eligible(decision)
    if not elig["eligible"]:
        raise ExecutionGateError(
            "Execution 只接受 CertifiedDecision；裸 DecisionSnapshot "
            "没有认证资格（请先 certify_decision）。")
    return {
        "executed": True,
        "decision_id": decision.decision_id,
        "certificate_id": decision.certificate_id,
        "instruction": "T+1 周收盘确认成交",
    }
