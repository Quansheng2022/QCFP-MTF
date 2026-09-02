# coding: utf-8
"""Critical Path Runtime 事件测试（Release 2：新 17 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.decision_snapshot import DecisionSnapshot
from QCFP_MTF.monitoring.critical_path_observability import \
    build_runtime_critical_path, decision_critical_path_trace


def _events(wave_status="OK", pit_status="OK"):
    return {
        "evidence_available": {"status": "OK", "latency_ms": 5,
                               "version": "ev", "input_hash": "i1",
                               "output_hash": "o1", "reason": ""},
        "pit_valid": {"status": pit_status, "latency_ms": 3,
                      "version": "pit_B", "input_hash": "i2",
                      "output_hash": "o2", "reason": ""},
        "permission_generated": {"status": "OK", "latency_ms": 2,
                                 "version": "ALLOW", "input_hash": "i3",
                                 "output_hash": "o3", "reason": ""},
        "wave_generated": {"status": wave_status, "latency_ms": 4,
                           "version": "ACTIVE", "input_hash": "i4",
                           "output_hash": "o4", "reason": ""},
        "governance_finalized": {"status": "OK", "latency_ms": 1,
                                 "version": "GOV", "input_hash": "i5",
                                 "output_hash": "o5", "reason": ""},
        "snapshot_committed": {"status": "OK", "latency_ms": 1,
                               "version": "S", "input_hash": "i6",
                               "output_hash": "o6", "reason": ""},
        "ledger_hash_committed": {"status": "OK", "latency_ms": 2,
                                  "version": "run1", "input_hash": "i7",
                                  "output_hash": "o7", "reason": ""},
        "execution_instruction_generated": {"status": "OK",
                                            "latency_ms": 1,
                                            "version": "",
                                            "input_hash": "i8",
                                            "output_hash": "o8",
                                            "reason": ""},
    }


def test_runtime_path_all_ok():
    r = build_runtime_critical_path(_events())
    assert r["all_ok"] is True


def test_skipped_not_blocker():
    ev = _events()
    ev["wave_generated"] = {"status": "SKIPPED", "reason": "无 Wave 证据"}
    ev["governance_finalized"]["status"] = "SKIPPED"
    r = build_runtime_critical_path(ev)
    assert r["all_ok"] is True
    assert r["first_blocker"] is None


def test_missing_stage_is_anomaly():
    ev = _events()
    del ev["ledger_hash_committed"]
    r = build_runtime_critical_path(ev)
    assert r["first_blocker"] == "ledger_hash_committed"


def test_decision_trace_answer():
    snap = DecisionSnapshot(
        decision_id="d1", stock_code="01951", decision_date="2026-08-21",
        institutional_state="ACCUMULATION",
        institutional_permission="ALLOW", permission_cap="TRADE",
        exit_event_kind="NONE", exit_event_reason="", setup_type="BREAKOUT",
        prev_fsm_state="FLAT", next_fsm_state="FLAT",
        previous_position=0.0, target_position=0.0)
    ev = _events()
    ev["wave_generated"]["status"] = "BLOCKED"
    ev["wave_generated"]["reason"] = "MATURE + ADD not allowed"
    r = decision_critical_path_trace(snap, ev)
    assert r["decision_id"] == "d1"
    assert "wave_generated" in r["critical_path_trace"]["hint"]
