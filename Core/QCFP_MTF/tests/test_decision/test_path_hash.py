# coding: utf-8
"""Decision Path Hash 测试（34 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.decision_snapshot import DecisionSnapshot
from QCFP_MTF.decision.path_hash import decision_path_hash


def _snap(target=0.04, perm="ALLOW", setup="BREAKOUT", fsm="TESTING"):
    return DecisionSnapshot(
        decision_id="d1", stock_code="01951", decision_date="2026-08-21",
        institutional_state="ACCUMULATION",
        institutional_permission=perm, permission_cap="TRADE",
        exit_event_kind="NONE", exit_event_reason="", setup_type=setup,
        prev_fsm_state="FLAT", next_fsm_state=fsm,
        previous_position=0.0, target_position=target,
        raw_target_position=0.10, participation_mode="EXPLORE",
        participation_cap=0.10, input_fingerprint="fp1",
        feature_manifest_hash="fmh1",
        context={"governance_proof": {"proof": "PASS"},
                 "execution_assumption": "T+1 周收盘确认成交"})


def test_path_hash_deterministic():
    assert decision_path_hash(_snap()) == decision_path_hash(_snap())


def test_path_hash_changes_with_logic():
    a = decision_path_hash(_snap(perm="ALLOW"))
    b = decision_path_hash(_snap(perm="BLOCK"))
    c = decision_path_hash(_snap(setup="PULLBACK"))
    assert a != b
    assert a != c


def test_path_hash_in_engine_context():
    from QCFP_MTF.config.settings import DEFAULT_SETTINGS
    from QCFP_MTF.decision.engine import evaluate
    row = {"stock_code": "T_PH", "decision_date": "2026-08-21",
           "c_state": "C↑", "f_state": "F↑", "p_state": "P↑",
           "prev_f_state": "F↑", "monthly_behavior_state": "Improving",
           "tactical_signal": "Breakout", "daily_state": "DAILY_BREAKOUT",
           "risk_level": "Medium", "des_score": 1,
           "chip_stability_confidence": "High", "data_quality": "B",
           "q_position_52w": 0.3}
    snap = evaluate(dict(row), "FLAT", 0.0, DEFAULT_SETTINGS)
    assert snap.context["decision_path_hash"]
    assert len(snap.context["decision_path_hash"]) == 16
