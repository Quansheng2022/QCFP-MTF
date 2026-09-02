# coding: utf-8
"""Field Lineage 接真实 Snapshot 测试（新 44 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.decision_snapshot import DecisionSnapshot
from QCFP_MTF.decision.field_lineage import field_lineage_from_snapshot


def _snap():
    return DecisionSnapshot(
        decision_id="d1", stock_code="01951", decision_date="2026-08-21",
        institutional_state="ACCUMULATION",
        institutional_permission="ALLOW", permission_cap="TRADE",
        exit_event_kind="NONE", exit_event_reason="", setup_type="BREAKOUT",
        prev_fsm_state="FLAT", next_fsm_state="TESTING",
        previous_position=0.0, target_position=0.08,
        raw_target_position=0.10, binding_constraint="liquidity_cap",
        rule_version="GOV-2.5.0",
        constraint_trace={"steps": [
            {"constraint": "liquidity_cap", "output_value": 0.08,
             "reason": "LIQUIDITY_LIMIT", "version": "1.0"}]})


def test_lineage_from_snapshot():
    r = field_lineage_from_snapshot(_snap())
    assert r["binding_constraint"] == "liquidity_cap"
    assert r["traces_to_pit_evidence"] is True
    nodes = {n["field"] for n in r["chain"]}
    assert "final_target" in nodes
    assert "raw_target" in nodes
    assert "liquidity_cap" in nodes
    assert "permission" in nodes
    for node in r["chain"]:
        assert node["rule_id"]
        assert node["version"]
        assert node["source_snapshot_id"] == "d1"
