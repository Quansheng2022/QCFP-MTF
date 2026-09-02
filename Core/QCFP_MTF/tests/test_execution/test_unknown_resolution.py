# coding: utf-8
"""UNKNOWN Resolution Pipeline 测试（P0-6）"""

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.execution.unknown_resolution import (
    assert_no_blind_resend, unknown_resolution_metrics_from_events,
    unknown_resolution_pipeline)


def _ev(event_type, decision_id="d1", intent="O-1", time="2026-08-21 "
        "10:00:00", payload=None, seq=1):
    return {"event_seq": seq, "event_type": event_type,
            "decision_id": decision_id, "order_intent_id": intent,
            "event_time": time, "payload": payload or {}}


def test_unknown_then_resolved_filled():
    events = [
        _ev("ORDER_UNKNOWN", time="2026-08-21 10:00:00", seq=1),
        _ev("UNKNOWN_QUERY", time="2026-08-21 10:00:10", seq=2),
        _ev("UNKNOWN_QUERY", time="2026-08-21 10:00:20", seq=3),
        _ev("UNKNOWN_RESOLVED", time="2026-08-21 10:00:30",
            payload={"resolution_status": "RESOLVED_FILLED"}, seq=4),
    ]
    r = unknown_resolution_pipeline(events)
    assert r["status"] == "RESOLVED_FILLED"
    assert r["resolved"] is True
    assert r["risk_unblocked"] is True
    assert r["no_new_risk"] is False
    assert r["query_attempt_count"] == 2
    assert r["resolution_latency_ms"] == 30000


def test_unknown_unresolved_no_new_risk():
    events = [
        _ev("ORDER_UNKNOWN", time="2026-08-21 10:00:00", seq=1),
        _ev("UNKNOWN_QUERY", time="2026-08-21 10:00:10", seq=2),
    ]
    r = unknown_resolution_pipeline(events)
    assert r["status"] == "UNRESOLVED_UNKNOWN"
    assert r["resolved"] is False
    assert r["risk_unblocked"] is False
    assert r["no_new_risk"] is True


def _event_table(conn):
    conn.execute(
        "CREATE TABLE qcfp_runtime_event_ledger (event_seq INTEGER "
        "PRIMARY KEY AUTOINCREMENT, event_id TEXT, event_type TEXT, "
        "event_time TEXT, release_id TEXT, decision_id TEXT, "
        "order_intent_id TEXT, broker_order_id TEXT, payload TEXT)")


def test_metrics_blind_resend_hard_gate():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _event_table(conn)
    rows = [
        ("E1", "ORDER_SENT", "d1", "O-1"),
        ("E2", "ORDER_UNKNOWN", "d1", "O-1"),
        ("E3", "ORDER_SENT", "d1", "O-1"),   # blind resend
        ("E4", "UNKNOWN_RESOLVED", "d1", "O-1"),
    ]
    for i, (eid, et, dec, intent) in enumerate(rows, 1):
        conn.execute(
            "INSERT INTO qcfp_runtime_event_ledger (event_seq, event_id, "
            "event_type, event_time, release_id, decision_id, "
            "order_intent_id, payload) VALUES (?,?,?,?,?,?,?,?)",
            (i, eid, et, "2026-08-21 10:00:00", "REL-A", dec, intent,
             '{"resolution_status": "RESOLVED_NO_ORDER"}' if et
             == "UNKNOWN_RESOLVED" else "{}"))
    m = unknown_resolution_metrics_from_events(
        conn, "REL-A", "2026-08-21", "2026-08-21")
    assert m["unknown_count"] == 1
    assert m["resolved_unknown"] == 1
    assert m["unresolved_unknown"] == 0
    assert m["blind_resend_count"] == 1      # Hard Gate 必须被报告
    # unresolved UNKNOWN 存在时禁止第二张等价 order
    conn.execute(
        "DELETE FROM qcfp_runtime_event_ledger WHERE event_id='E4'")
    b = assert_no_blind_resend(conn, "d1", "O-1", new_order_id="O-2")
    assert b["blocked"] is True
    assert b["reason"] == "UNRESOLVED_UNKNOWN_EXISTS"


def test_no_unknown_no_metrics():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _event_table(conn)
    conn.execute(
        "INSERT INTO qcfp_runtime_event_ledger (event_seq, event_id, "
        "event_type, event_time, release_id, decision_id, "
        "order_intent_id, payload) VALUES (1,'E1','ORDER_SENT',"
        "'2026-08-21','REL-A','d1','O-1','{}')")
    m = unknown_resolution_metrics_from_events(
        conn, "REL-A", "2026-08-21", "2026-08-21")
    assert m["unknown_count"] == 0
    assert m["blind_resend_count"] == 0
