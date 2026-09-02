# coding: utf-8
"""DecisionPathHash 强化测试（新 45 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.decision_snapshot import DecisionSnapshot
from QCFP_MTF.decision.path_hash import decision_path_hash, \
    path_hash_determinism_check


def _snap(caps=None, perm="ALLOW"):
    return DecisionSnapshot(
        decision_id="d1", stock_code="01951", decision_date="2026-08-21",
        institutional_state="ACCUMULATION",
        institutional_permission=perm, permission_cap="TRADE",
        exit_event_kind="NONE", exit_event_reason="", setup_type="BREAKOUT",
        prev_fsm_state="FLAT", next_fsm_state="TESTING",
        previous_position=0.0, target_position=0.08,
        raw_target_position=0.10, binding_constraint="liquidity_cap",
        model_version="QCFP-MTF-2.5.0", rule_version="GOV-2.5.0",
        settings_hash="cfg1", input_fingerprint="fp1",
        feature_manifest_hash="fmh1",
        context={"governance_proof": {"proof": "PASS"},
                 "governance_caps": caps or {
                     "portfolio_cap": 1.0, "liquidity_cap": 1.0,
                     "execution_cap": 1.0, "drawdown_cap": 1.0,
                     "sector_cap": 1.0, "theme_cap": 1.0,
                     "permission_cap": 1.0, "risk_cap": 1.0,
                     "data_quality_cap": 1.0},
                 "execution_assumption": "T+1 周收盘确认成交"})


def test_path_hash_differs_with_config():
    a = decision_path_hash(_snap(caps={"liquidity_cap": 0.2}))
    b = decision_path_hash(_snap(caps={"liquidity_cap": 0.5}))
    assert a != b


def test_path_hash_same_identity_same_hash():
    a = decision_path_hash(_snap())
    b = decision_path_hash(_snap())
    assert a == b


def test_determinism_check_consistent():
    r = path_hash_determinism_check({"a": 1}, "H", {"a": 1}, "H")
    assert r["verdict"] == "CONSISTENT"


def test_determinism_failure_detected():
    r = path_hash_determinism_check({"a": 1}, "H1", {"a": 1}, "H2")
    assert r["verdict"] == "DETERMINISM_FAILURE"
