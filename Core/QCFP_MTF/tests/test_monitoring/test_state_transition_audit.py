# coding: utf-8
"""State Transition Audit 测试（86 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.monitoring.state_transition_audit import \
    state_transition_audit


def _transitions():
    return [
        {"from": "DISCOVERY", "to": "CONFIRMING", "reason": "confirm",
         "duration": 3, "decision_impact": 0.1},
        {"from": "CONFIRMING", "to": "ACTIVE", "reason": "confirm",
         "duration": 2, "decision_impact": 0.2},
        {"from": "ACTIVE", "to": "CONFIRMING", "reason": "recheck",
         "duration": 1, "decision_impact": 0.0},
        {"from": "CONFIRMING", "to": "ACTIVE", "reason": "confirm",
         "duration": 1, "decision_impact": 0.0},
        {"from": "DISCOVERY", "to": "MATURE", "reason": "jump",
         "duration": 5, "decision_impact": 0.0},
    ]


def test_audit_detects_issues():
    allowed = [("DISCOVERY", "CONFIRMING"), ("CONFIRMING", "ACTIVE"),
               ("ACTIVE", "CONFIRMING")]
    r = state_transition_audit(_transitions(), allowed=allowed)
    assert r["verdict"] == "SIMPLIFY_FSM"
    assert [list(x) for x in r["impossible_transitions"]] == \
        [["DISCOVERY", "MATURE"]]
    assert r["oscillations"] != []
    assert r["no_decision_meaning_count"] >= 2


def test_audit_healthy():
    transitions = [
        {"from": "A", "to": "B", "reason": "x", "duration": 1,
         "decision_impact": 0.1},
        {"from": "B", "to": "C", "reason": "y", "duration": 2,
         "decision_impact": 0.2},
    ]
    r = state_transition_audit(transitions,
                               allowed=[("A", "B"), ("B", "C")])
    assert r["verdict"] == "HEALTHY"
    assert r["never_used_transitions"] == []


def test_never_used_detected():
    r = state_transition_audit(
        [{"from": "A", "to": "B", "reason": "x", "duration": 1,
          "decision_impact": 0.1}],
        allowed=[("A", "B"), ("B", "C")])
    assert [list(x) for x in r["never_used_transitions"]] == \
        [["B", "C"]]
