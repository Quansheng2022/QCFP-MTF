# coding: utf-8
"""ProposalAction Classifier（QCFP-MTF Convergence：新 2 号）

唯一 ProposalAction 分类函数（禁止 Engine 内临时三元表达式）：
    prev=0, proposal>0        → ENTRY
    proposal > prev > 0       → ADD
    proposal == prev > 0      → HOLD
    0 < proposal < prev       → REDUCE
    prev>0, proposal=0        → EXIT
    prev=proposal=0           → NO_TRADE
"""


def proposal_action(previous_position, proposal_target) -> str:
    prev = float(previous_position or 0.0)
    prop = float(proposal_target or 0.0)
    if prev <= 1e-9 and prop <= 1e-9:
        return "NO_TRADE"
    if prev <= 1e-9 and prop > 1e-9:
        return "ENTRY"
    if prop > prev + 1e-9:
        return "ADD"
    if abs(prop - prev) <= 1e-9:
        return "HOLD"
    if prop > 1e-9:
        return "REDUCE"
    return "EXIT"


def proposal_action_matrix() -> list:
    """覆盖验收矩阵。"""
    return [
        {"previous": 0.0, "proposal": 0.0, "expected": "NO_TRADE"},
        {"previous": 0.0, "proposal": 0.05, "expected": "ENTRY"},
        {"previous": 0.05, "proposal": 0.10, "expected": "ADD"},
        {"previous": 0.10, "proposal": 0.10, "expected": "HOLD"},
        {"previous": 0.10, "proposal": 0.05, "expected": "REDUCE"},
        {"previous": 0.10, "proposal": 0.0, "expected": "EXIT"},
    ]
