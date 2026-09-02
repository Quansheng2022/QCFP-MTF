# coding: utf-8
"""Runtime Event Ledger 双链测试（Sprint 3/4 + Runtime Evidence Wiring）"""

import json
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.execution.runtime_event_ledger import (
    RUNTIME_EVENT_TYPES, append_incident_event, append_reactivation_event,
    append_recovery_event, append_replay_event, append_runtime_event,
    ensure_runtime_event_table, trusted_checkpoint,
    validate_runtime_identity, verify_runtime_event_chain)


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _init_schema(conn)
    return conn


def _init_schema(conn):
    """显式 Schema（生产由 sql/create_qcfp_tables.sql 迁移拥有）。"""
    ensure_runtime_event_table(conn)
    conn.execute(
        "CREATE TABLE qcfp_decision_ledger (id INTEGER PRIMARY KEY "
        "AUTOINCREMENT, decision_id TEXT, run_id TEXT, stock_code TEXT, "
        "decision_date TEXT, context TEXT, status TEXT DEFAULT 'ACTIVE')")
    conn.execute(
        "CREATE TABLE qcfp_decision_certificate (certificate_id TEXT "
        "PRIMARY KEY, decision_id TEXT, release_id TEXT, snapshot_hash "
        "TEXT, evidence_pack_hash TEXT, created_at TEXT)")
    conn.execute(
        "INSERT INTO qcfp_decision_ledger (decision_id, run_id, "
        "stock_code, decision_date, context, status) VALUES (?,?,?,?,?,?)",
        ("d1", "RUN-1", "00700", "2026-08-21",
         json.dumps({"release_identity": {"release_id": "REL-A"}}),
         "ACTIVE"))
    conn.execute(
        "INSERT INTO qcfp_decision_certificate (certificate_id, "
        "decision_id, release_id) VALUES (?,?,?)",
        ("CERT-1", "d1", "REL-A"))


def _event(eid, etype, **kw):
    e = {"event_id": eid, "event_type": etype, "event_time": "2026-08-28",
         "decision_id": "d1", "release_id": "REL-A",
         "execution_mode": "PAPER", "stock_code": "00700",
         "broker_order_id": "B-1", "filled_qty": 100,
         "fill_price": 10.0, "commission": 1.0, "stamp_duty": 1.0,
         "exchange_fee": 0.5, "other_fee": 0.0,
         "internal_position": 0.2, "broker_position": 0.2,
         "reconciliation_status": "IN_SYNC"}
    e.update(kw)
    return e


def test_append_and_verify_chain():
    conn = _conn()
    append_runtime_event(conn, _event("E1", "ORDER_SENT"))
    append_runtime_event(conn, _event("E2", "FILL"))
    r = verify_runtime_event_chain(conn)
    assert r["verified"] is True
    assert r["checked"] == 2
    assert r["chain_tail"]


def test_chain_break_detected():
    conn = _conn()
    append_runtime_event(conn, _event("E1", "ORDER_SENT"))
    append_runtime_event(conn, _event("E2", "FILL"))
    conn.execute("UPDATE qcfp_runtime_event_ledger SET "
                 "previous_event_hash='TAMPERED' WHERE event_id='E2'")
    r = verify_runtime_event_chain(conn)
    assert r["verified"] is False
    assert any(m["event_id"] == "E2" and m["type"] == "PREV_HASH_BREAK"
               for m in r["mismatches"])


def test_payload_tamper_detected_by_recompute():
    """第 8A 项：改 filled_qty / 费用 / broker_position 必须被
    payload_hash 重算发现，不只是链指针。"""
    conn = _conn()
    append_runtime_event(conn, _event("E1", "ORDER_SENT"))
    append_runtime_event(conn, _event("E2", "FILL"))
    conn.execute("UPDATE qcfp_runtime_event_ledger SET "
                 "filled_qty=999 WHERE event_id='E2'")
    r = verify_runtime_event_chain(conn)
    assert r["verified"] is False
    assert any(m["type"] in ("PAYLOAD_HASH_MISMATCH",
                             "CURRENT_HASH_MISMATCH")
               for m in r["mismatches"])


def test_identity_mismatch_rejected():
    """第 2 项：release_id 与决策台账不一致 → EVENT_APPEND_REJECTED。"""
    conn = _conn()
    r = append_runtime_event(
        conn, _event("E1", "ORDER_SENT", release_id="REL-WRONG"))
    assert r["rejected"] is True
    assert r["reason"] == "EVENT_APPEND_REJECTED"
    assert "RELEASE_ID_MISMATCH_WITH_DECISION" in r["identity"]["reasons"]
    assert verify_runtime_event_chain(conn)["checked"] == 0


def test_small_live_certificate_required():
    """第 2 项：SMALL_LIVE 缺 certificate / certificate 身份不符 → 拒绝。"""
    conn = _conn()
    r = append_runtime_event(
        conn, _event("E1", "ORDER_SENT", execution_mode="SMALL_LIVE"))
    assert r["rejected"] is True
    assert "CERTIFICATE_ID_REQUIRED" in r["identity"]["reasons"]
    r2 = append_runtime_event(
        conn, _event("E2", "ORDER_SENT", execution_mode="SMALL_LIVE",
                     certificate_id="CERT-BAD"))
    assert r2["rejected"] is True
    assert "CERTIFICATE_NOT_FOUND" in r2["identity"]["reasons"]
    r3 = append_runtime_event(
        conn, _event("E3", "ORDER_SENT", execution_mode="SMALL_LIVE",
                     certificate_id="CERT-1"))
    assert r3["rejected"] is False


def test_incident_recovery_reactivation_chain():
    """第 9 项：Incident → Recovery → Replay → Reactivation
    全链真实持久化到 Runtime Event Ledger。"""
    conn = _conn()
    cp = trusted_checkpoint(conn, "INC-123", "REL-A",
                            decision_id="d1",
                            decision_path_hash="H",
                            internal_position=0.2,
                            broker_position=0.2,
                            config_hash="CFG")
    append_incident_event(conn, "INC-123", "REL-A",
                          checkpoint=cp)
    append_recovery_event(conn, "INC-123", "REL-A",
                          root_cause="data fix", fix="applied")
    append_replay_event(conn, "INC-123", "REL-A",
                        replay_hash="RH", verified=True)
    append_reactivation_event(conn, "INC-123", "REL-A",
                              certificate_id="CERT-1",
                              replay_hash="RH",
                              approval_identity="GOV-1")
    r = verify_runtime_event_chain(conn)
    assert r["verified"] is True
    assert r["checked"] == 4
    types = [row["event_type"] for row in conn.execute(
        "SELECT event_type FROM qcfp_runtime_event_ledger "
        "ORDER BY event_seq")]
    assert types == ["INCIDENT", "RECOVERY", "REPLAY", "REACTIVATION"]


def test_event_types_defined():
    assert "ORDER_UNKNOWN" in RUNTIME_EVENT_TYPES
    assert "REACTIVATION" in RUNTIME_EVENT_TYPES
    assert len(RUNTIME_EVENT_TYPES) == 16
