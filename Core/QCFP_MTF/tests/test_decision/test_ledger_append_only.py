# coding: utf-8
"""Ledger 事实链测试（新 4 号：content-sensitive + append-only + 双链）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.common.db import connect
from QCFP_MTF.decision.decision_ledger import (_last_run_hash,
                                               compute_data_snapshot_id,
                                               dataset_manifest_hash,
                                               invalidate_snapshot,
                                               ledger_event,
                                               verify_ledger_chain)


def test_data_snapshot_id_content_sensitive_delegate():
    conn = connect()
    try:
        sid = compute_data_snapshot_id(conn)
        assert sid == dataset_manifest_hash(conn)
        assert len(sid) == 16
    finally:
        conn.close()


def test_manifest_changes_when_table_set_changes():
    conn = connect()
    try:
        h = dataset_manifest_hash(conn)
        h2 = dataset_manifest_hash(conn, tables=("qcfp_weekly_tactical",))
        assert h != h2
    finally:
        conn.close()


def test_invalidate_is_append_only_event():
    conn = connect()
    try:
        # 不存在的决策 → 返回 0（append 事件未插入），绝无 UPDATE 语义
        assert invalidate_snapshot(
            conn, "T_APPEND_NONEXIST", "R_TEST", "superseded") == 0
        assert ledger_event(
            conn, "T_APPEND_NONEXIST", "DECISION_INVALIDATED") == 0
    finally:
        conn.close()


def test_run_hash_deterministic_and_chainable():
    row = {"decision_id": "d1", "stock_code": "01951",
           "decision_date": "2026-08-21",
           "institutional_permission": "ALLOW",
           "previous_fsm_state": "FLAT", "next_fsm_state": "TESTING",
           "previous_position": 0.0, "raw_target": 0.1,
           "final_target": 0.08, "primary_reason": "WAVE_CONFIRM",
           "model_version": "M", "rule_version": "R",
           "schema_version": "S", "settings_hash": "H",
           "input_fingerprint": "F"}
    from QCFP_MTF.decision.decision_ledger import _ledger_hash
    h1 = _ledger_hash("", row)
    h2 = _ledger_hash("prev", row)
    assert h1 != h2
    # run 链头：无历史 run 时为空
    conn = connect()
    try:
        assert _last_run_hash(conn, "T_NO_SUCH_RUN") == ""
        assert verify_ledger_chain(conn, run_id="T_NO_SUCH_RUN")[
            "run_chain_tail"] == ""
    finally:
        conn.close()
