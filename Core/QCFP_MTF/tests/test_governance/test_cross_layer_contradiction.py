# coding: utf-8
"""Cross-Layer Contradiction Audit 测试（87 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.cross_layer_contradiction import \
    cross_layer_contradiction_audit


def test_block_wave_active_target_zero_explained():
    r = cross_layer_contradiction_audit({
        "institutional_permission": "BLOCK",
        "wave_state": "ACTIVE",
        "fsm_action": "ADD",
        "final_target": 0.0})
    assert r["verdict"] == "EXPLAINED"
    assert r["issues"] == []
    assert r["explained"] != []
    assert "participation denied" in r["explained"][0].lower() \
        or "denied" in r["explained"][0].lower()


def test_block_with_positive_target_violation():
    r = cross_layer_contradiction_audit({
        "institutional_permission": "BLOCK",
        "wave_state": "ACTIVE",
        "fsm_action": "ADD",
        "final_target": 0.40})
    assert r["verdict"] == "VIOLATION"
    assert r["issues"][0]["type"] == "AUTHORITY_VIOLATION"


def test_consistent_layers():
    r = cross_layer_contradiction_audit({
        "institutional_permission": "ALLOW",
        "wave_state": "ACTIVE",
        "fsm_action": "ADD",
        "final_target": 0.30})
    assert r["verdict"] == "CONSISTENT"


def test_proposal_vs_decision_explained():
    r = cross_layer_contradiction_audit({
        "institutional_permission": "TEST",
        "wave_state": "CONFIRMING",
        "fsm_action": "TEST",
        "final_target": 0.20,
        "proposal_action": "ADD"})
    assert r["verdict"] == "EXPLAINED"
    assert r["single_canonical_decision"] is True
