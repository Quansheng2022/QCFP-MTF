# coding: utf-8
"""DecisionSchemaContract + Migration 测试（新 41 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.schema_contract import SCHEMA_FIELD_STATUS, \
    SCHEMA_MIGRATIONS, schema_change_release_gate, schema_migration_rule, \
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
        "context": {},
    }


def test_new_required_fields():
    assert SCHEMA_FIELD_STATUS["wave_stage"] == "REQUIRED"
    assert SCHEMA_FIELD_STATUS["binding_constraint"] == "REQUIRED"
    assert SCHEMA_FIELD_STATUS["legacy_action_signal"] == "FORBIDDEN"


def test_forbidden_legacy_action_signal():
    fields = _valid_fields()
    fields["legacy_action_signal"] = "BUY"
    r = snapshot_replayability("DECISION-1.2", fields)
    assert r["verdict"] == "NOT_REPLAYABLE"


def test_migration_defined():
    assert SCHEMA_MIGRATIONS["DECISION-1.1"] == "DECISION-1.2"
    r = schema_migration_rule("DECISION-1.1", "DECISION-1.2")
    assert r["migration_defined"] is True


def test_release_rejected_without_migration():
    r = schema_change_release_gate("DECISION-1.1", "DECISION-9.9")
    assert r["verdict"] == "RELEASE_REJECTED"
    assert r["allowed"] is False
    r2 = schema_change_release_gate("DECISION-1.1", "DECISION-1.2")
    assert r2["allowed"] is True
