# coding: utf-8
"""Runtime Evidence Wiring 跨切项：Schema 迁移 + 主链不可绕过"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))


def _sql() -> str:
    return (Path(CORE_DIR) / "QCFP_MTF" / "sql" /
            "create_qcfp_tables.sql").read_text(encoding="utf-8")


def test_runtime_tables_in_sql_migration():
    """跨切项 A：三张 Runtime 表必须由 SQL 迁移拥有。"""
    sql = _sql()
    assert "CREATE TABLE IF NOT EXISTS qcfp_runtime_event_ledger" in sql
    assert "CREATE TABLE IF NOT EXISTS qcfp_research_outcome" in sql
    assert "CREATE TABLE IF NOT EXISTS qcfp_decision_certificate" in sql


def test_runtime_schema_fields_present():
    """跨切项 B：runtime_event_seq / execution_mode / broker_order_id /
    incident_id / outcome_hash 必须纳入 Schema Migration。"""
    sql = _sql()
    for field in ("event_seq", "execution_mode", "broker_order_id",
                  "incident_id", "outcome_hash", "certificate_id"):
        assert field in sql, f"SQL 迁移缺少字段 {field}"


def test_outcome_fields_contract():
    from QCFP_MTF.research.research_outcome import OUTCOME_FIELDS
    for field in ("outcome_hash", "future_aware", "research_only",
                  "source_data_snapshot_id", "horizon_end"):
        assert field in OUTCOME_FIELDS


def test_negative_cap_cannot_reach_broker():
    """跨切项 D：deployment_cap=-0.1 绝不能进入 Broker Order——
    dispatch 层必须 INVALID_DEPLOYMENT_CAP 拦截。"""
    from QCFP_MTF.decision.certified_decision import CertifiedDecision
    from QCFP_MTF.execution.broker_adapter import BrokerAdapter
    from QCFP_MTF.execution.execution_context import ExecutionContext, \
        dispatch_runtime

    class RecordingAdapter(BrokerAdapter):
        def __init__(self):
            self.submits = []

        def submit_order(self, order_intent):
            self.submits.append(order_intent)
            return {"status": "ACK", "broker_order_id": "B-1"}

        def query_order(self, broker_order_id):
            return {"status": "ACK"}

        def query_fills(self, broker_order_id):
            return []

        def query_positions(self, account_id, stock_code=None):
            return {}

        def cancel_order(self, broker_order_id):
            return {"status": "CANCELLED"}

    cert = CertifiedDecision(
        decision_id="d1", certificate_id="CERT-1",
        snapshot={"target_position": 0.2}, safety_status="NORMAL",
        acceptance_verdict="ACCEPTED", evidence_ref={},
        release_id="REL-A")
    adapter = RecordingAdapter()
    r = dispatch_runtime(
        cert,
        ExecutionContext(execution_mode="SMALL_LIVE", account_id="R1",
                         broker_name="BROKER_REAL", deployment_cap=-0.1),
        execution_services={"broker_adapter": adapter})
    assert r["dispatched"] is False
    assert r["reason"] == "INVALID_DEPLOYMENT_CAP"
    assert adapter.submits == []


def test_valid_cap_dispatches_small_live():
    from QCFP_MTF.decision.certified_decision import CertifiedDecision
    from QCFP_MTF.execution.broker_adapter import BrokerAdapter
    from QCFP_MTF.execution.execution_context import ExecutionContext, \
        dispatch_runtime

    class RecordingAdapter(BrokerAdapter):
        def __init__(self):
            self.submits = []

        def submit_order(self, order_intent):
            self.submits.append(order_intent)
            return {"status": "ACK", "broker_order_id": "B-1"}

        def query_order(self, broker_order_id):
            return {"status": "ACK"}

        def query_fills(self, broker_order_id):
            return []

        def query_positions(self, account_id, stock_code=None):
            return {}

        def cancel_order(self, broker_order_id):
            return {"status": "CANCELLED"}

    cert = CertifiedDecision(
        decision_id="d1", certificate_id="CERT-1",
        snapshot={"target_position": 0.3}, safety_status="NORMAL",
        acceptance_verdict="ACCEPTED", evidence_ref={},
        release_id="REL-A")
    adapter = RecordingAdapter()
    r = dispatch_runtime(
        cert,
        ExecutionContext(execution_mode="SMALL_LIVE", account_id="R1",
                         broker_name="BROKER_REAL", deployment_cap=0.05),
        execution_services={"broker_adapter": adapter})
    assert r["dispatched"] is True
    assert r["deployment"]["deployment_target"] == 0.05
    assert len(adapter.submits) == 1
    assert adapter.submits[0]["quantity"] == 0.05
