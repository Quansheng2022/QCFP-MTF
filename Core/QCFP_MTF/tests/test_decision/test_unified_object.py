# coding: utf-8
"""Unified Decision Object 测试（11 号：统一决策对象）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.decision_snapshot import DecisionSnapshot
from QCFP_MTF.decision.object import (CONSUMERS, UnifiedDecision,
                                      build_unified_decision,
                                      composite_hash,
                                      validate_unified_decision)


def _fake_snap():
    return DecisionSnapshot(
        decision_id="01951_2024-02-01",
        stock_code="01951", decision_date="2024-02-01",
        institutional_state="ACCUMULATION",
        institutional_permission="ALLOW",
        permission_cap="TRADE", exit_event_kind="NONE",
        exit_event_reason="", setup_type="BREAKOUT",
        prev_fsm_state="FLAT", next_fsm_state="TESTING",
        previous_position=0.0, target_position=0.02,
        decision_path=("evidence", "institutional", "fsm"),
        participation_mode="EXPLORE", participation_cap=0.10)


def test_build_unified_decision():
    snap = _fake_snap()
    obj = build_unified_decision(snap, mode="REPLAY")
    assert isinstance(obj, UnifiedDecision)
    assert obj.snapshot["target_position"] == 0.02
    assert obj.version_hash
    assert obj.decision_hash
    assert "REPLAY" in obj.consumers
    # mode/consumers 不影响 decision_hash
    obj2 = build_unified_decision(snap, mode="LIVE")
    assert obj.decision_hash == obj2.decision_hash


def test_validate_unified_decision():
    obj = build_unified_decision(_fake_snap(), mode="AUDIT")
    assert validate_unified_decision(obj) == []
    assert validate_unified_decision(obj, required_mode="AUDIT") == []
    assert validate_unified_decision(obj, required_mode="LIVE")


def test_composite_hash_stable():
    a = composite_hash({"model": "M", "rule": "R", "input": "I"})
    b = composite_hash({"rule": "R", "input": "I", "model": "M"})
    assert a == b
    c = composite_hash({"model": "M", "rule": "R", "input": "J"})
    assert a != c


def test_consumers_constant():
    assert set(CONSUMERS) == {"LIVE", "BACKTEST", "REPLAY", "SHADOW",
                              "REPORT", "AUDIT"}


def test_top_level_wave_stage_governed_evidence():
    snap = _fake_snap()
    snap = DecisionSnapshot(
        decision_id="01951_2024-02-01",
        stock_code="01951", decision_date="2024-02-01",
        institutional_state="ACCUMULATION",
        institutional_permission="ALLOW",
        permission_cap="TRADE", exit_event_kind="NONE",
        exit_event_reason="", setup_type="BREAKOUT",
        prev_fsm_state="FLAT", next_fsm_state="TESTING",
        previous_position=0.0, target_position=0.02,
        participation_mode="EXPLORE", participation_cap=0.10,
        input_fingerprint="fp1", data_snapshot_id="ds1",
        pit_grade="B", evidence_grade="B",
        context={"governance_proof": {"governed_target": 0.05}})
    obj = build_unified_decision(
        snap, mode="REPLAY", wave={"stage": "ACTIVE", "strength": 0.8})
    assert obj.wave_stage == "ACTIVE"
    assert obj.governed_target == 0.05
    assert obj.evidence["input_fingerprint"] == "fp1"
    assert obj.evidence["data_snapshot_id"] == "ds1"
    assert obj.evidence["pit_grade"] == "B"
