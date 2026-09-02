# coding: utf-8
"""execution_mode 不改变 Canonical Decision 测试（Sprint 1）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.decision.engine import evaluate
from QCFP_MTF.execution.execution_context import ExecutionContext, \
    assert_mode_not_in_decision_hash, dispatch_runtime, \
    same_decision_across_modes, validate_execution_context, \
    validate_execution_mode


def test_only_three_modes():
    assert validate_execution_mode("SHADOW")["valid"] is True
    assert validate_execution_mode("PAPER")["valid"] is True
    assert validate_execution_mode("SMALL_LIVE")["valid"] is True
    assert validate_execution_mode("HFT")["valid"] is False


def test_mode_not_in_path_hash():
    r = assert_mode_not_in_decision_hash(
        {"final_target": 0.2, "execution_mode": "SHADOW"})
    assert r["violation"] is True
    r2 = assert_mode_not_in_decision_hash({"final_target": 0.2})
    assert r2["violation"] is False


def _evidence():
    return {
        "stock_code": "T_M", "decision_date": "2026-08-21",
        "c_state": "C↑", "f_state": "F↑", "p_state": "P↑",
        "prev_f_state": "F↑", "monthly_behavior_state": "Improving",
        "tactical_signal": "Breakout", "daily_state": "DAILY_BREAKOUT",
        "risk_level": "Low", "des_score": 0, "wave_strength": 1.0,
        "chip_stability_confidence": "High", "data_quality": "B",
        "q_position_52w": 0.2, "q_trend_score": 55.0,
        "market_context": "risk_on", "cbi_state": "CBI_STABLE",
        "catalyst_score": 1.0,
    }


def test_same_decision_across_modes():
    release = {"release_id": "REL-A", "release_manifest_hash": "MH-A",
               "evidence_pack_hash": "EH-A"}
    r = same_decision_across_modes(
        evaluate, _evidence(), release, DEFAULT_SETTINGS)
    assert r["canonical_identical"] is True
    assert r["verdict"] == "MODE_INVARIANT"
    # 三种 mode 的 FinalTarget/PathHash 完全一致
    final_targets = {v["final_target"] for v in r["results"].values()}
    assert len(final_targets) == 1


def test_context_as_dict():
    c = ExecutionContext(execution_mode="PAPER", run_id="r1",
                         account_id="a1", deployment_cap=0.05,
                         broker_name="paper")
    assert c.as_dict()["execution_mode"] == "PAPER"


def test_validate_execution_context_modes():
    """第 1 项：SHADOW 不允许 deployment_cap；PAPER 必须 account+broker；
    SMALL_LIVE 必须 real account+broker+cap。"""
    assert validate_execution_context(
        ExecutionContext(execution_mode="SHADOW"))["valid"] is True
    bad_shadow = validate_execution_context(
        ExecutionContext(execution_mode="SHADOW", deployment_cap=0.05))
    assert bad_shadow["valid"] is False
    assert "SHADOW_DEPLOYMENT_CAP_NOT_APPLICABLE" in bad_shadow["reasons"]
    assert validate_execution_context(
        ExecutionContext(execution_mode="PAPER", account_id="P1",
                         broker_name="PAPER_BROKER"))["valid"] is True
    bad_paper = validate_execution_context(
        ExecutionContext(execution_mode="PAPER"))
    assert bad_paper["valid"] is False
    assert "PAPER_ACCOUNT_REQUIRED" in bad_paper["reasons"]
    live = validate_execution_context(
        ExecutionContext(execution_mode="SMALL_LIVE", account_id="R1",
                         broker_name="BROKER_REAL", deployment_cap=0.05))
    assert live["valid"] is True
    bad_live = validate_execution_context(
        ExecutionContext(execution_mode="SMALL_LIVE", account_id="R1",
                         broker_name="BROKER_REAL"))
    assert bad_live["valid"] is False
    assert "DEPLOYMENT_CAP_REQUIRED" in bad_live["reasons"]


def test_dispatch_shadow_never_submits():
    """第 1 项：SHADOW 只记录 WOULD_EXECUTE，永不提交订单。"""
    from QCFP_MTF.decision.decision_snapshot import DecisionSnapshot
    snap = DecisionSnapshot(
        decision_id="d1", stock_code="01951", decision_date="2026-08-21",
        institutional_state="ACCUMULATION",
        institutional_permission="ALLOW", permission_cap="TRADE",
        exit_event_kind="NONE", exit_event_reason="", setup_type="BREAKOUT",
        prev_fsm_state="FLAT", next_fsm_state="TESTING",
        previous_position=0.0, target_position=0.2,
        release_id="REL-A")
    r = dispatch_runtime(
        snap, ExecutionContext(execution_mode="SHADOW"))
    assert r["dispatched"] is True
    assert r["orders_submitted"] is False
    assert r["would_execute"] is True


def test_dispatch_paper_requires_eligibility():
    """第 1 项：PAPER 先资格检查，裸 Snapshot 不允许下模拟订单。"""
    from QCFP_MTF.decision.decision_snapshot import DecisionSnapshot
    snap = DecisionSnapshot(
        decision_id="d1", stock_code="01951", decision_date="2026-08-21",
        institutional_state="ACCUMULATION",
        institutional_permission="ALLOW", permission_cap="TRADE",
        exit_event_kind="NONE", exit_event_reason="", setup_type="BREAKOUT",
        prev_fsm_state="FLAT", next_fsm_state="TESTING",
        previous_position=0.0, target_position=0.2,
        release_id="REL-A")
    r = dispatch_runtime(
        snap,
        ExecutionContext(execution_mode="PAPER", account_id="P1",
                         broker_name="PAPER_BROKER"),
        execution_services={"current_position": 0.0,
                            "simulator": None})
    assert r["dispatched"] is False
    assert "CERTIFIED_DECISION_REQUIRED" in r["reason"]


def _certified(target=0.2, decision_id="d1", certificate_id="CERT-1",
               release_id="REL-A"):
    from QCFP_MTF.decision.certified_decision import CertifiedDecision
    return CertifiedDecision(
        decision_id=decision_id, certificate_id=certificate_id,
        snapshot={"target_position": target, "stock_code": "01951"},
        safety_status="NORMAL", acceptance_verdict="ACCEPTED",
        evidence_ref={}, release_id=release_id)


def _recording_adapter():
    from QCFP_MTF.execution.broker_adapter import BrokerAdapter

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

    return RecordingAdapter()


def test_dispatch_paper_reads_certified_target():
    """P0：CertifiedDecision 的 FinalTarget 在 snapshot 中——
    Paper 必须读到 20%，不能读成 0。"""
    class FakeSimulator:
        def execute_order(self, intent):
            return {"status": "FILLED",
                    "filled_qty": intent["quantity"],
                    "position": intent["current_position"]
                    + intent["delta"]}
    cert = _certified(target=0.2)
    r = dispatch_runtime(
        cert,
        ExecutionContext(execution_mode="PAPER", account_id="P1",
                         broker_name="PAPER_BROKER"),
        execution_services={"current_position": 0.0,
                            "simulator": FakeSimulator()})
    assert r["dispatched"] is True
    assert r["orders_submitted"] is True
    assert r["result"]["intent"]["side"] == "BUY"
    assert r["result"]["intent"]["delta"] == 0.2


def test_dispatch_small_live_delta_order():
    """P0：Small-Live 必须下 Delta（DeploymentTarget-CurrentPosition），
    不能直接下 DeploymentTarget。"""
    adapter = _recording_adapter()
    cert = _certified(target=0.3)
    r = dispatch_runtime(
        cert,
        ExecutionContext(execution_mode="SMALL_LIVE", account_id="R1",
                         broker_name="BROKER_REAL", deployment_cap=0.05),
        execution_services={"broker_adapter": adapter,
                            "current_position": 0.04})
    assert r["dispatched"] is True
    assert r["deployment"]["deployment_target"] == 0.05
    assert len(adapter.submits) == 1
    assert adapter.submits[0]["quantity"] == 0.01
    assert adapter.submits[0]["delta"] == 0.01


def test_dispatch_small_live_broker_event_unpersisted_fails():
    """P0：Broker Event 落库失败（identity 缺失）→ 不能返回
    dispatched=True，必须 BROKER_RESPONSE_UNPERSISTED:NO_NEW_RISK。"""
    import json
    import sqlite3
    from QCFP_MTF.execution.runtime_event_ledger import \
        ensure_runtime_event_table
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_runtime_event_table(conn)
    conn.execute(
        "CREATE TABLE qcfp_decision_ledger (id INTEGER PRIMARY KEY "
        "AUTOINCREMENT, decision_id TEXT, context TEXT, status TEXT)")
    # decision 存在但 release identity 不匹配/证书不存在 → 事件被拒
    conn.execute(
        "INSERT INTO qcfp_decision_ledger VALUES "
        "(1,'d1','{\"release_identity\": {\"release_id\": \"OTHER\"}}',"
        "'ACTIVE')")
    adapter = _recording_adapter()
    cert = _certified(target=0.2)
    r = dispatch_runtime(
        cert,
        ExecutionContext(execution_mode="SMALL_LIVE", account_id="R1",
                         broker_name="BROKER_REAL", deployment_cap=0.05),
        execution_services={"broker_adapter": adapter,
                            "current_position": 0.0,
                            "event_time": "2026-08-29"},
        conn=conn)
    assert r["dispatched"] is False
    assert r["reason"] == "BROKER_RESPONSE_UNPERSISTED:NO_NEW_RISK"
    assert r["orders_submitted"] is False
