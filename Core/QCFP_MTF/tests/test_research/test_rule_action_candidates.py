# coding: utf-8
"""Rule Interaction → KEEP/MERGE/DROP 候选测试（新 64 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.research.rule_interaction_audit import rule_action_candidates, \
    rule_interaction_audit


def _audit(results):
    return rule_interaction_audit(results)


def test_redundant_merges():
    a = _audit({
        "NEITHER": {"sharpe": 0.30, "mdd": -0.20},
        "A_ONLY": {"sharpe": 0.70, "mdd": -0.12},
        "B_ONLY": {"sharpe": 0.32, "mdd": -0.20},
        "A_AND_B": {"sharpe": 0.71, "mdd": -0.12}})
    r = rule_action_candidates(a)
    assert r["action"] == "MERGE"


def test_dominated_drops():
    a = _audit({
        "NEITHER": {"sharpe": 0.30, "mdd": -0.20},
        "A_ONLY": {"sharpe": 0.80, "mdd": -0.10},
        "B_ONLY": {"sharpe": 0.40, "mdd": -0.19},
        "A_AND_B": {"sharpe": 0.55, "mdd": -0.15}})
    r = rule_action_candidates(a)
    assert r["action"] == "DROP"


def test_complementary_keeps():
    a = _audit({
        "NEITHER": {"sharpe": 0.30, "mdd": -0.20},
        "A_ONLY": {"sharpe": 0.50, "mdd": -0.18},
        "B_ONLY": {"sharpe": 0.52, "mdd": -0.18},
        "A_AND_B": {"sharpe": 0.85, "mdd": -0.10}})
    r = rule_action_candidates(a)
    assert r["action"] == "KEEP"
