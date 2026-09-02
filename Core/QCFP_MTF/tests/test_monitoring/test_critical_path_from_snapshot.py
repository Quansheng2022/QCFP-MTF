# coding: utf-8
"""Critical Path 接入真实 Snapshot 测试（新 16 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.decision_snapshot import DecisionSnapshot
from QCFP_MTF.monitoring.critical_path_observability import \
    critical_path_from_snapshot


def _snap(pit="B"):
    return DecisionSnapshot(
        decision_id="d1", stock_code="01951", decision_date="2026-08-21",
        institutional_state="ACCUMULATION",
        institutional_permission="ALLOW", permission_cap="TRADE",
        exit_event_kind="NONE", exit_event_reason="", setup_type="BREAKOUT",
        prev_fsm_state="FLAT", next_fsm_state="TESTING",
        previous_position=0.0, target_position=0.2, pit_grade=pit,
        run_id="run_1", input_fingerprint="FP1", schema_version="S",
        rule_version="R", binding_constraint="portfolio_cap",
        wave_stage="ACTIVE",
        context={"governance_proof": {"proof": "PASS"}})


def test_path_from_snapshot_all_ok():
    r = critical_path_from_snapshot(_snap(), ledger_ok=True,
                                    execution_ok=True)
    assert r["all_ok"] is True
    assert r["first_blocker"] is None
    assert len(r["path"]) == 8


def test_pit_failure_located():
    r = critical_path_from_snapshot(_snap(pit="C"), ledger_ok=True)
    assert r["all_ok"] is False
    assert r["first_blocker"] == "pit_valid"


def test_ledger_failure_located():
    r = critical_path_from_snapshot(_snap(), ledger_ok=False)
    assert r["first_blocker"] == "ledger_hash_committed"


def test_execution_pending_not_blocker():
    """Execution 未生成 = PENDING（不是 FAIL），不算阻塞。"""
    r = critical_path_from_snapshot(_snap(), ledger_ok=True)
    stages = {s["stage"]: s["status"] for s in r["path"]}
    assert stages["execution_instruction_generated"] == "PENDING"
    assert r["all_ok"] is False
