# coding: utf-8
"""Rule Interaction Audit 测试（64 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.research.rule_interaction_audit import \
    interception_overlap, rule_interaction_audit


def test_complementary_rules():
    r = rule_interaction_audit({
        "NEITHER": {"sharpe": 0.30, "mdd": -0.20},
        "A_ONLY": {"sharpe": 0.50, "mdd": -0.18},
        "B_ONLY": {"sharpe": 0.52, "mdd": -0.18},
        "A_AND_B": {"sharpe": 0.85, "mdd": -0.10},
    })
    assert r["relation"] == "COMPLEMENTARY"


def test_redundant_rule():
    r = rule_interaction_audit({
        "NEITHER": {"sharpe": 0.30, "mdd": -0.20},
        "A_ONLY": {"sharpe": 0.70, "mdd": -0.12},
        "B_ONLY": {"sharpe": 0.32, "mdd": -0.20},
        "A_AND_B": {"sharpe": 0.71, "mdd": -0.12},
    })
    assert r["relation"] == "REDUNDANT"


def test_conflicting_rules():
    r = rule_interaction_audit({
        "NEITHER": {"sharpe": 0.30, "mdd": -0.20},
        "A_ONLY": {"sharpe": 0.55, "mdd": -0.16},
        "B_ONLY": {"sharpe": 0.57, "mdd": -0.16},
        "A_AND_B": {"sharpe": 0.20, "mdd": -0.25},
    })
    assert r["relation"] == "CONFLICTING"


def test_dominated_rule():
    r = rule_interaction_audit({
        "NEITHER": {"sharpe": 0.30, "mdd": -0.20},
        "A_ONLY": {"sharpe": 0.80, "mdd": -0.10},
        "B_ONLY": {"sharpe": 0.40, "mdd": -0.19},
        "A_AND_B": {"sharpe": 0.55, "mdd": -0.15},
    })
    assert r["relation"] == "DOMINATED"


def test_interception_overlap_high():
    a = [f"s{i}" for i in range(1, 21)]
    b = [f"s{i}" for i in range(1, 20)]
    r = interception_overlap(a, b)
    assert r["overlap_ratio"] == 0.95
    assert r["redundancy_candidate"] is True


def test_interception_overlap_low():
    r = interception_overlap(["s1", "s2"], ["s3", "s4"])
    assert r["redundancy_candidate"] is False
