# coding: utf-8
"""State Transition 价值审计测试（新 86 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.monitoring.state_transition_audit import state_value_audit


def test_states_with_value_kept():
    r = state_value_audit(
        ["TESTING", "HOLDING", "WATCH"],
        target_impact={"TESTING": 0.5, "HOLDING": 0.3, "WATCH": 0.0})
    assert r["states"]["TESTING"]["verdict"] == "HAS_VALUE"
    assert r["no_independent_value"] == ["WATCH"]
    assert r["compression_candidates"] == ["WATCH"]


def test_all_states_valuable():
    r = state_value_audit(["ENTRY", "HOLD"],
                          target_impact={"ENTRY": 0.4, "HOLD": 0.2})
    assert r["no_independent_value"] == []
