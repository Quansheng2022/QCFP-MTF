# coding: utf-8
"""Schema Contract Release Hard Gate 测试（Release 3：新 21 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.schema_contract import SCHEMA_FIELD_STATUS, \
    schema_release_hard_gate


def _fields():
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
    for f in ("release_id", "release_manifest_hash", "decision_path_hash",
              "canonical_action", "wave_proposal_target"):
        assert SCHEMA_FIELD_STATUS[f] == "REQUIRED"


def test_direct_replay_unchanged():
    r = schema_release_hard_gate("DECISION-1.2", _fields())
    assert r["verdict"] == "DIRECT_REPLAY"
    assert r["allowed"] is True


def test_migration_required_with_migration():
    r = schema_release_hard_gate("DECISION-1.2", _fields(),
                                 from_version="DECISION-1.1",
                                 migration_exists=True)
    assert r["verdict"] == "MIGRATION_REQUIRED"
    assert r["allowed"] is True


def test_release_rejected_without_migration():
    r = schema_release_hard_gate("DECISION-1.3", _fields(),
                                 from_version="DECISION-1.2",
                                 migration_exists=False)
    assert r["verdict"] == "RELEASE_REJECTED"
    assert r["allowed"] is False


def test_forbidden_field_not_replayable():
    fields = _fields()
    fields["future_return"] = 0.5
    r = schema_release_hard_gate("DECISION-1.2", fields)
    assert r["verdict"] == "NOT_REPLAYABLE"
    assert r["allowed"] is False
