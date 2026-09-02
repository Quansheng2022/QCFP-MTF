# coding: utf-8
"""Report Contract 测试（P0-7 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.decision_snapshot import DecisionSnapshot
from QCFP_MTF.report.contract import (ReportContractError,
                                      assert_report_ledger_only,
                                      report_consumes_only)


def _snap():
    return DecisionSnapshot(
        decision_id="d1", stock_code="01951", decision_date="2026-08-21",
        institutional_state="ACCUMULATION",
        institutional_permission="ALLOW", permission_cap="TRADE",
        exit_event_kind="NONE", exit_event_reason="", setup_type="BREAKOUT",
        prev_fsm_state="FLAT", next_fsm_state="TESTING",
        previous_position=0.0, target_position=0.04,
        primary_reason="WAVE_CONFIRM")


def test_report_matches_ledger():
    snap = _snap()
    ledger = {"institutional_permission": "ALLOW",
              "previous_fsm_state": "FLAT", "next_fsm_state": "TESTING",
              "final_target": 0.04, "primary_reason": "WAVE_CONFIRM"}
    assert report_consumes_only(snap, ledger)["ok"] is True


def test_report_recomputation_rejected():
    snap = _snap()
    ledger = {"institutional_permission": "BLOCK",
              "previous_fsm_state": "FLAT", "next_fsm_state": "TESTING",
              "final_target": 0.0, "primary_reason": "PERMISSION_BLOCK"}
    try:
        assert_report_ledger_only(snap, ledger)
        raise AssertionError("should raise")
    except ReportContractError:
        pass
