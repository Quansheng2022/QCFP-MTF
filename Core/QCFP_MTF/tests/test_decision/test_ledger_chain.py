# coding: utf-8
"""Ledger Immutable Hash Chain 测试（P0-2 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.common.db import connect
from QCFP_MTF.decision.decision_ledger import _ledger_hash, \
    verify_ledger_chain


def test_ledger_hash_deterministic():
    row = {"decision_id": "d1", "stock_code": "01951",
           "decision_date": "2026-08-21",
           "institutional_permission": "ALLOW",
           "previous_fsm_state": "FLAT", "next_fsm_state": "TESTING",
           "previous_position": 0.0, "raw_target": 0.1,
           "final_target": 0.08, "primary_reason": "WAVE_CONFIRM",
           "model_version": "M", "rule_version": "R",
           "schema_version": "S", "settings_hash": "H",
           "input_fingerprint": "F"}
    assert _ledger_hash("", row) == _ledger_hash("", row)
    assert _ledger_hash("prev1", row) != _ledger_hash("", row)
    assert len(_ledger_hash("", row)) == 16


def test_verify_ledger_chain_runs():
    conn = connect()
    try:
        r = verify_ledger_chain(conn)
        assert "verified" in r
        assert "chain_tail" in r
        assert r["n_rows"] >= 0
    finally:
        conn.close()
