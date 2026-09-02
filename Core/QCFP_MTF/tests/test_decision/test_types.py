# coding: utf-8
"""Proposal/Decision 类型隔离测试（23 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.types import (CanonicalDecision,
                                      ExecutionInstruction,
                                      GovernedProposal,
                                      ProposalTypeError,
                                      TradeIdea, TradeProposal,
                                      assert_executable_input)


def test_proposal_cannot_be_executed():
    proposal = TradeProposal(stock_code="01951", requested_target=0.7)
    try:
        assert_executable_input(proposal)
        raise AssertionError("should raise")
    except ProposalTypeError:
        pass


def test_decision_can_be_executed():
    decision = CanonicalDecision(decision_id="D1", stock_code="01951",
                                 decision_date="2026-08-21",
                                 final_target=0.04)
    assert_executable_input(decision)   # 不抛错


def test_type_hierarchy():
    idea = TradeIdea(stock_code="01951", proposal_strength=0.82)
    proposal = TradeProposal(stock_code="01951", requested_target=0.7,
                             fsm_proposal="BUILD")
    governed = GovernedProposal(stock_code="01951", governed_target=0.35,
                                binding_constraint="LIQUIDITY_CAP")
    decision = CanonicalDecision(decision_id="D1", stock_code="01951",
                                 decision_date="2026-08-21",
                                 final_target=0.35)
    instruction = ExecutionInstruction(decision_id="D1",
                                       stock_code="01951",
                                       executable_target=0.35)
    assert idea.proposal_strength == 0.82
    assert proposal.requested_target == 0.7
    assert governed.binding_constraint == "LIQUIDITY_CAP"
    assert instruction.executable_target == 0.35
