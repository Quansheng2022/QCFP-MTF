# coding: utf-8
"""Broker Adapter 契约测试（Sprint 3 + Runtime Evidence Wiring）"""

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.execution.broker_adapter import BrokerAdapter, \
    assert_broker_adapter_contract, broker_timeout_result, \
    normalize_broker_response, resolve_broker_unknown


class PaperAdapter(BrokerAdapter):
    def submit_order(self, order_intent):
        return {"status": "ACK"}

    def query_order(self, broker_order_id):
        return {"status": "FILLED"}

    def query_fills(self, broker_order_id):
        return []

    def query_positions(self, account_id, stock_code=None):
        return {}

    def cancel_order(self, broker_order_id):
        return {"status": "CANCELLED"}


class BadAdapter(BrokerAdapter):
    def calculate_target(self):
        return 0.5


def test_adapter_contract_ok():
    r = assert_broker_adapter_contract(PaperAdapter())
    assert r["contract_ok"] is True


def test_adapter_with_decision_logic_fails():
    r = assert_broker_adapter_contract(BadAdapter())
    assert r["contract_ok"] is False
    assert "calculate_target" in r["forbidden_methods_present"]


def test_timeout_unknown_preserved():
    r = broker_timeout_result("B-1")
    assert r["status"] == "UNKNOWN"
    assert r["block_new_order"] is True
    assert r["action"] == "QUERY_BROKER_AND_RECONCILE"


class HalfAdapter(BrokerAdapter):
    """只 override 部分方法：其余仍是 NotImplemented。"""
    def submit_order(self, order_intent):
        return {"status": "ACK"}


def test_contract_requires_real_override():
    """第 8 项：Contract Ready ≠ Broker Reality Ready——
    未 override 的方法必须 NOT_IMPLEMENTED，不能 contract_ok=True。"""
    r = assert_broker_adapter_contract(HalfAdapter())
    assert r["contract_ok"] is False
    assert "query_order" in r["not_implemented"]
    assert "cancel_order" in r["not_implemented"]


def test_normalize_broker_response():
    """第 8 项：统一 Broker Response Schema。"""
    raw = {"status": "FILLED", "broker_order_id": "B-1",
           "source_timestamp": "2026-08-28T10:00:00Z",
           "fill": {"fill_id": "F1", "quantity": 100, "price": 10.0,
                    "commission": 1.0, "stamp_duty": 1.0,
                    "exchange_fee": 0.5, "other_fee": 0.0}}
    n = normalize_broker_response(raw, "BROKER_REAL",
                                  request_id="REQ-1")
    assert n["normalized_status"] == "FILLED"
    assert n["broker_order_id"] == "B-1"
    assert n["quantity"] == 100
    assert n["commission"] == 1.0
    # 未知状态 → UNKNOWN（绝不默认 ACK）
    n2 = normalize_broker_response(
        {"status": "BROKER_PENDING_X", "broker_order_id": "B-2"},
        "BROKER_REAL")
    assert n2["normalized_status"] == "UNKNOWN"


def _runtime_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    from QCFP_MTF.execution.runtime_event_ledger import \
        ensure_runtime_event_table
    ensure_runtime_event_table(conn)
    conn.execute(
        "CREATE TABLE qcfp_decision_ledger (id INTEGER PRIMARY KEY "
        "AUTOINCREMENT, decision_id TEXT, run_id TEXT, stock_code TEXT, "
        "decision_date TEXT, context TEXT, status TEXT DEFAULT 'ACTIVE')")
    conn.execute(
        "INSERT INTO qcfp_decision_ledger (decision_id, run_id, "
        "stock_code, decision_date, context, status) VALUES "
        "('d1','RUN-1','00700','2026-08-21',"
        "'{\"release_identity\": {\"release_id\": \"REL-A\"}}','ACTIVE')")
    conn.execute(
        "CREATE TABLE qcfp_decision_certificate (certificate_id TEXT "
        "PRIMARY KEY, decision_id TEXT, release_id TEXT)")
    conn.execute(
        "INSERT INTO qcfp_decision_certificate VALUES "
        "('CERT-1','d1','REL-A')")
    return conn


def test_resolve_broker_unknown():
    """第 8 项：query → fills → positions → reconciliation；
    只有 Resolved 才允许恢复新风险。"""
    conn = _runtime_conn()
    unresolved = resolve_broker_unknown(
        conn, "B-1", "REL-A", decision_id="d1", queries={
            "query_order": {"status": "PENDING"},
            "query_positions": {"quantity": None},
            "canonical_target": 0.2, "internal_position": 0.1})
    assert unresolved["resolved"] is False
    assert unresolved["new_risk_allowed"] is False
    resolved = resolve_broker_unknown(
        conn, "B-2", "REL-A", decision_id="d1",
        certificate_id="CERT-1", queries={
            "query_order": {"status": "FILLED"},
            "query_fills": [{"fill_id": "F1", "quantity": 100,
                             "price": 10.0}],
            "query_positions": {"quantity": 100}})
    assert resolved["resolved"] is True
    assert resolved["new_risk_allowed"] is True
