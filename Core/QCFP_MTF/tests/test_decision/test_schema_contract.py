# coding: utf-8
"""DecisionSchemaContract 测试（41 号：Schema 契约与迁移规则）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.schema_contract import schema_contract, \
    snapshot_replayability


def _valid_fields():
    return {
        "decision_id": "d1", "stock_code": "01951",
        "decision_date": "2026-08-21",
        "institutional_permission": "ALLOW", "target_position": 0.2,
        "wave_stage": "ACTIVE", "binding_constraint": "portfolio_cap",
        "release_id": "REL-1", "release_manifest_hash": "MH1",
        "decision_path_hash": "PH1", "canonical_action": "ENTRY",
        "wave_proposal_target": 0.15,
        "previous_position": 0.0, "raw_target_position": 0.25,
        "next_fsm_state": "TESTING", "primary_reason": "WAVE_CONFIRM",
        "context": {}, "decision_hash": "abc", "run_id": "r1",
    }


def test_valid_snapshot_replayable():
    c = schema_contract("DECISION-1.1", _valid_fields())
    assert c["valid"] is True
    assert c["violations"] == []
    r = snapshot_replayability("DECISION-1.1", _valid_fields())
    assert r["verdict"] == "REPLAY"


def test_missing_required_requires_migration():
    fields = _valid_fields()
    del fields["target_position"]
    r = snapshot_replayability("DECISION-1.1", fields)
    assert r["verdict"] == "MIGRATE"


def test_forbidden_field_not_replayable():
    fields = _valid_fields()
    fields["future_return"] = 0.5
    c = schema_contract("DECISION-1.1", fields)
    assert c["valid"] is False
    assert "future_return" in c["forbidden_present"]
    r = snapshot_replayability("DECISION-1.1", fields)
    assert r["verdict"] == "NOT_REPLAYABLE"


def test_forbidden_field_none_is_ignored():
    fields = _valid_fields()
    fields["future_return"] = None
    c = schema_contract("DECISION-1.1", fields)
    assert c["valid"] is True
