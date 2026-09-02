# coding: utf-8
"""Critical Path 接真实 Runtime 测试（新 57 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.decision_snapshot import DecisionSnapshot
from QCFP_MTF.monitoring.critical_path_observability import \
    decision_layer_outcome


def _snap(pit="B", target=0.2):
    return DecisionSnapshot(
        decision_id="d1", stock_code="01951", decision_date="2026-08-21",
        institutional_state="ACCUMULATION",
        institutional_permission="ALLOW", permission_cap="TRADE",
        exit_event_kind="NONE", exit_event_reason="", setup_type="BREAKOUT",
        prev_fsm_state="FLAT", next_fsm_state="TESTING",
        previous_position=0.0, target_position=target, pit_grade=pit,
        run_id="run_1", input_fingerprint="FP",
        binding_constraint="portfolio_cap", wave_stage="ACTIVE",
        context={"governance_proof": {"proof": "PASS"}})


def test_certified_decision_all_layers_pass():
    r = decision_layer_outcome(_snap())
    assert r["outcome"] == "CERTIFIED_DECISION"
    assert r["filtered_at"] is None


def test_no_trade_distinct_from_filtered():
    r = decision_layer_outcome(_snap(target=0.0))
    assert r["outcome"] == "NO_TRADE"
    assert r["layer"] == "FINAL_TARGET"


def test_filtered_at_pit():
    r = decision_layer_outcome(_snap(pit="D"))
    assert r["outcome"] == "FILTERED"
    assert r["filtered_at"] == "pit_valid"
