# coding: utf-8
"""Paper Order Pipeline 测试（Sprint 2）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.decision_snapshot import DecisionSnapshot
from QCFP_MTF.execution.execution_context import ExecutionContext
from QCFP_MTF.execution.paper_pipeline import map_simulator_status, \
    order_intent, paper_calibration_samples, paper_daily_reconciliation, \
    paper_order_pipeline


def _snap(target=0.2):
    return DecisionSnapshot(
        decision_id="d1", stock_code="01951", decision_date="2026-08-21",
        institutional_state="ACCUMULATION",
        institutional_permission="ALLOW", permission_cap="TRADE",
        exit_event_kind="NONE", exit_event_reason="", setup_type="BREAKOUT",
        prev_fsm_state="FLAT", next_fsm_state="TESTING",
        previous_position=0.1, target_position=target,
        primary_reason="WAVE_CONFIRM", context={})


class FakeSimulator:
    def execute_order(self, intent):
        return {"status": "FILLED", "filled_qty": intent["quantity"],
                "position": intent["current_position"]
                + intent["delta"]}


class StatusSimulator:
    def __init__(self, status, filled_qty=None):
        self.status = status
        self.filled_qty = filled_qty

    def execute_order(self, intent):
        return {"status": self.status, "filled_qty": self.filled_qty,
                "position": 0.2}


def test_order_intent_delta():
    r = order_intent(0.10, 0.20)
    assert r["side"] == "BUY"
    assert r["delta"] == 0.10
    r2 = order_intent(0.10, 0.10)
    assert r2["side"] == "NONE"


def test_paper_pipeline_uses_osm_and_simulator():
    ctx = ExecutionContext(execution_mode="PAPER")
    r = paper_order_pipeline(_snap(), ctx, 0.10, FakeSimulator())
    assert r["evidence_source"] == "PAPER_PROXY"
    assert r["intent"]["side"] == "BUY"
    assert r["reconciliation"]["status"] == "IN_SYNC"


def test_paper_pipeline_rejects_non_paper():
    ctx = ExecutionContext(execution_mode="SHADOW")
    r = paper_order_pipeline(_snap(), ctx, 0.0, FakeSimulator())
    assert "error" in r


def test_eod_reconciliation_coverage():
    r = paper_daily_reconciliation(
        {"00700": {"position": 0.2, "broker_position": 0.2}},
        {"00700": 0.2})
    assert r["reconciliation_coverage"] == 1.0
    assert r["unresolved_unknown"] == 0
    assert r["reconciliation_status"] == "MATCHED"
    assert r["layers"]["position"]["status"] == "MATCHED"


def test_status_mapping_unique():
    """第 5 项：唯一 Status Mapping——未知状态 → timeout，绝不 ACK。"""
    assert map_simulator_status("FILLED") == "ack_full"
    assert map_simulator_status("PARTIAL") == "ack_partial"
    assert map_simulator_status("REJECTED") == "reject"
    assert map_simulator_status("CANCELLED") == "cancel"
    assert map_simulator_status("UNKNOWN") == "timeout"
    assert map_simulator_status("BROKER_PENDING_X") == "timeout"


def test_paper_reject_and_unknown():
    """第 5 项：REJECTED → reject()；UNKNOWN → timeout()（block new order）。"""
    ctx = ExecutionContext(execution_mode="PAPER")
    r_rej = paper_order_pipeline(
        _snap(), ctx, 0.1, StatusSimulator("REJECTED", filled_qty=0))
    assert r_rej["ack_state"] == "REJECTED"
    assert r_rej["status_transition"] == "reject"
    r_unk = paper_order_pipeline(
        _snap(), ctx, 0.1, StatusSimulator("UNKNOWN"))
    assert r_unk["ack_state"] == "UNKNOWN"
    assert r_unk["status_transition"] == "timeout"
    r_unknown_status = paper_order_pipeline(
        _snap(), ctx, 0.1, StatusSimulator("BROKER_PENDING_X"))
    assert r_unknown_status["ack_state"] == "UNKNOWN"


def test_unknown_then_resend_blocked():
    """第 5 项：UNKNOWN 后盲重发必须被阻止（DUPLICATE_BLOCKED）。"""
    from QCFP_MTF.execution.order_state_machine import OrderStateMachine
    osm = OrderStateMachine()
    osm.send("O-1", 100)
    osm.timeout("O-1")
    r = osm.send("O-1", 100)
    assert r["state"] == "DUPLICATE_BLOCKED"


def test_eod_missing_broker_is_unknown():
    """第 6 项：缺 broker_position 绝不能拿 internal 伪装一致。"""
    r = paper_daily_reconciliation(
        {"00700": {"position": 0.2}}, {"00700": 0.2})
    assert r["results"]["00700"]["status"] == "UNKNOWN"
    assert r["unresolved_unknown"] == 1
    assert r["layers"]["position"]["status"] == "UNKNOWN"
    assert r["reconciliation_status"] == "UNKNOWN"


def test_eod_five_layers_independent():
    """P0-5：Decision/Order/Fill/Position/Cash-Fee 五层独立对账。"""
    r = paper_daily_reconciliation(
        {"00700": {"position": 0.2, "broker_position": 0.2}},
        {"00700": 0.2},
        order_records={"00700": {"broker_order_id": "B-1"}},
        fill_records={"00700": {"filled_qty": 0.2}},
        fee_records={"00700": {"estimated_fee": 1.0,
                               "realized_fee": 1.0}})
    assert set(r["layers"]) == {"decision", "order", "fill",
                                "position", "cash_fee"}
    assert r["layers"]["decision"]["status"] == "MATCHED"
    assert r["layers"]["order"]["status"] == "MATCHED"
    assert r["layers"]["fill"]["status"] == "MATCHED"
    assert r["layers"]["position"]["status"] == "MATCHED"
    assert r["layers"]["cash_fee"]["status"] == "MATCHED"
    assert r["reconciliation_status"] == "MATCHED"


def test_eod_fee_mismatch_is_layer_mismatch():
    r = paper_daily_reconciliation(
        {"00700": {"position": 0.2, "broker_position": 0.2}},
        {"00700": 0.2},
        fee_records={"00700": {"estimated_fee": 1.0,
                               "realized_fee": 3.0}})
    assert r["layers"]["cash_fee"]["status"] == "MISMATCH"
    assert r["reconciliation_status"] == "MISMATCH"


def test_eod_coverage_excludes_unexpected():
    """第 6 项：coverage = matched / expected；unexpected broker
    positions 单独报告，不塞进 coverage。"""
    r = paper_daily_reconciliation(
        {"00700": {"position": 0.2, "broker_position": 0.2},
         "99999": {"position": 0.1, "broker_position": 0.1}},
        {"00700": 0.2})
    assert r["reconciliation_coverage"] == 1.0
    assert r["unexpected_broker_positions"] == ["99999"]


def test_calibration_samples_aggregate():
    """第 6 项：Calibration 从 Paper Fill 样本聚合，禁止自动改参数。"""
    events = [{"payload": {"calibration": {
        "estimated_slippage": 10.0, "realized_slippage": 12.0,
        "estimated_fill_ratio": 1.0, "realized_fill_ratio": 0.8,
        "estimated_exit_days": 1.0, "realized_exit_days": 2.0,
        "estimated_participation": 0.1, "realized_participation": 0.8}}}]
    report = paper_calibration_samples(events)
    assert report["dimensions"]
    assert report["auto_param_modify_forbidden"] is True
