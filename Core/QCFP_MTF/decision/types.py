# coding: utf-8
"""Proposal / Decision 类型隔离（QCFP-MTF 2.8：23 号）

    TradeIdea → TradeProposal → GovernedProposal → CanonicalDecision →
    ExecutionInstruction

原则：上游只能"建议"，只有 Governance 能"决定"；
TradeProposal 无法被 Execution Engine 直接消费。
"""

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class TradeIdea:
    """Wave 产生：机会意图（不含仓位）。"""
    stock_code: str
    proposal_strength: float = 0.0
    idea_type: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class TradeProposal:
    """FSM/Sizing 产生：建议仓位（未过治理）。"""
    stock_code: str
    requested_target: float = 0.0
    fsm_proposal: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class GovernedProposal:
    """Governance 处理后的提案（cap 已应用）。"""
    stock_code: str
    governed_target: float = 0.0
    binding_constraint: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class CanonicalDecision:
    """唯一正式决策（Governance 生成）。"""
    decision_id: str
    stock_code: str
    decision_date: str
    final_target: float = 0.0
    reason_codes: tuple = field(default_factory=tuple)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["reason_codes"] = list(self.reason_codes)
        return d


@dataclass(frozen=True)
class ExecutionInstruction:
    """Execution 只能执行 Decision（不能消费 Proposal）。"""
    decision_id: str
    stock_code: str
    executable_target: float = 0.0

    def as_dict(self) -> dict:
        return asdict(self)


class ProposalTypeError(TypeError):
    pass


def assert_executable_input(obj) -> None:
    """Execution Engine 只接受 CanonicalDecision；TradeProposal 拒绝。"""
    if isinstance(obj, TradeProposal):
        raise ProposalTypeError(
            "类型隔离：TradeProposal 不能直接被 Execution Engine 消费，"
            "必须先经 Governance 生成 CanonicalDecision")
