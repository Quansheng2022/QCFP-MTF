# coding: utf-8
"""ProposalAction 分类验收矩阵（Convergence 新 2 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.action_classifier import proposal_action, \
    proposal_action_matrix


def test_matrix_all_cases():
    for case in proposal_action_matrix():
        assert proposal_action(case["previous"], case["proposal"]) \
            == case["expected"]


def test_confirming_flat_entry_not_add():
    """CONFIRMING + FLAT + proposal>0 → ENTRY（不是 ADD）。"""
    assert proposal_action(0.0, 0.05) == "ENTRY"


def test_add_requires_prev_positive():
    assert proposal_action(0.05, 0.10) == "ADD"
