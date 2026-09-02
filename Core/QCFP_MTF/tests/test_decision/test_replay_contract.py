# coding: utf-8
"""DecisionReplayContract 测试（21 号）

MTR Q4 Closure：Replay Eligibility（material/settings/blob/hash/
resolvability）属于 replay_contract，不在 decision_ledger——
测试与实现同址，不保留重复测试体系。"""

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.replay_contract import (
    DecisionReplayInput, assert_replay_certified,
    decision_replay_contract, replay_eligibility, replay_types)
from QCFP_MTF.decision.decision_snapshot import DecisionSnapshot


def _hash_settings(settings):
    import hashlib
    import json
    raw = json.dumps(settings, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def _snap(**kw):
    base = dict(
        decision_id="d1", stock_code="01951", decision_date="2026-08-21",
        input_fingerprint="IF-1",
        institutional_state="ACCUMULATION",
        institutional_permission="ALLOW", permission_cap="TRADE",
        exit_event_kind="NONE", exit_event_reason="", setup_type="BREAKOUT",
        prev_fsm_state="FLAT", next_fsm_state="TESTING",
        previous_position=0.0, target_position=0.2,
        decision_path=("evidence", "institutional", "fsm", "governance",
                       "final_target"),
        settings_hash=_hash_settings({"enabled": True}),
        release_id="REL-A",
        data_snapshot_id="DS-1", universe_snapshot_id="UV-1",
        model_version="QCFP-MTF-2.5.0",
        rule_version="GOV-2.5.0", schema_version="DECISION-1.1",
        production_manifest_hash="PM-1",
        participating_feature_hash="PF-1",
        context={"decision_path_hash": "DPH-1"})
    base.update(kw)
    return DecisionSnapshot(**base)


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE qcfp_model_registry (settings_hash TEXT, "
        "settings_blob TEXT)")
    import json
    conn.execute(
        "INSERT INTO qcfp_model_registry VALUES "
        "(?, ?)", (_hash_settings({"enabled": True}),
                   json.dumps({"enabled": True})))
    return conn


def _input(replay_type="decision"):
    return DecisionReplayInput(
        evidence_snapshot_id="EV-1", strategy_version="S1",
        engine_version="E1", governance_rule_version="GOV-1",
        config_hash="CFG1", feature_manifest_hash="FM1",
        universe_snapshot_id="U1", random_seed=42,
        replay_type=replay_type)


def test_replay_contract_exact_match():
    c = decision_replay_contract(_input(), "abc123", "abc123")
    assert c["exact_match"] is True
    assert c["production_ok"] is True
    assert_replay_certified(c)


def test_replay_contract_mismatch():
    c = decision_replay_contract(_input(), "abc123", "def456",
                                 mismatch_fields=["target_position"])
    assert c["exact_match"] is False
    assert c["production_ok"] is False
    try:
        assert_replay_certified(c)
        raise AssertionError("should raise")
    except ValueError:
        pass


def test_replay_types():
    assert replay_types() == ("data", "decision", "execution", "research")


def test_research_replay_not_production():
    c = decision_replay_contract(_input("research"), "a", "a")
    assert c["exact_match"] is True
    assert c["production_ok"] is False


# ---------------- Replay Eligibility（MTR Q8，归属 replay_contract）-----

def test_replay_eligible_when_material_complete():
    r = replay_eligibility(_conn(), _snap())
    assert r["replay_eligible"] is True
    assert r["settings_resolvable"] is True
    assert r["missing"] == []


def test_replay_eligible_when_settings_hash_matches():
    """settings_hash 必须等于 settings_blob canonical 序列化哈希。"""
    settings = {"model": {"version": "QCFP-MTF-2.5.0"}, "enabled": True}
    h = _hash_settings(settings)
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE qcfp_model_registry (settings_hash TEXT, "
        "settings_blob TEXT)")
    import json
    conn.execute(
        "INSERT INTO qcfp_model_registry VALUES (?, ?)",
        (h, json.dumps(settings)))
    r = replay_eligibility(conn, _snap(settings_hash=h))
    assert r["replay_eligible"] is True
    assert r["settings_reason"] == ""


def test_replay_ineligible_when_settings_not_registered():
    """settings 不能只存 Hash：settings_blob 不可解析 → 不可重放。"""
    conn = _conn()
    r = replay_eligibility(conn, _snap(settings_hash="SH-UNKNOWN"))
    assert r["replay_eligible"] is False
    assert any(m.startswith("settings_blob") for m in r["missing"])
    assert r["settings_reason"] == "SETTINGS_NOT_REGISTERED"


def test_replay_ineligible_when_settings_blob_empty():
    conn = _conn()
    conn.execute("DELETE FROM qcfp_model_registry")
    conn.execute("INSERT INTO qcfp_model_registry VALUES (?, '')",
                 (_hash_settings({"enabled": True}),))
    r = replay_eligibility(conn, _snap())
    assert r["replay_eligible"] is False
    assert r["settings_reason"] == "SETTINGS_EMPTY"


def test_replay_ineligible_when_settings_blob_invalid_json():
    conn = _conn()
    conn.execute("DELETE FROM qcfp_model_registry")
    conn.execute(
        "INSERT INTO qcfp_model_registry VALUES (?, '{broken')",
        (_hash_settings({"enabled": True}),))
    r = replay_eligibility(conn, _snap())
    assert r["replay_eligible"] is False
    assert r["settings_reason"] == "SETTINGS_UNPARSABLE"


def test_replay_ineligible_when_settings_hash_mismatch():
    """settings_blob 可解析但与 settings_hash 不一致 → 不可重放。"""
    conn = _conn()
    conn.execute("DELETE FROM qcfp_model_registry")
    conn.execute(
        "INSERT INTO qcfp_model_registry VALUES "
        "(?, '{\"enabled\": false}')",
        (_hash_settings({"enabled": True}),))
    r = replay_eligibility(conn, _snap())
    assert r["replay_eligible"] is False
    assert r["settings_reason"] == "SETTINGS_HASH_MISMATCH"


def test_replay_ineligible_when_identity_missing():
    r = replay_eligibility(
        _conn(), _snap(release_id="", universe_snapshot_id=""))
    assert r["replay_eligible"] is False
    assert "release_id" in r["missing"]
    assert "universe_snapshot_id" in r["missing"]


def test_replay_ineligible_when_decision_identity_missing():
    r = replay_eligibility(_conn(), _snap(decision_id="",
                                          input_fingerprint=""))
    assert r["replay_eligible"] is False
    assert "decision_id" in r["missing"]
    assert "input_fingerprint" in r["missing"]


def test_replay_ineligible_when_data_or_universe_snapshot_missing():
    r = replay_eligibility(_conn(), _snap(data_snapshot_id=""))
    assert r["replay_eligible"] is False
    assert "data_snapshot_id" in r["missing"]
    r = replay_eligibility(_conn(), _snap(universe_snapshot_id=""))
    assert r["replay_eligible"] is False
    assert "universe_snapshot_id" in r["missing"]


def test_replay_ineligible_when_decision_path_missing():
    r = replay_eligibility(_conn(), _snap(decision_path=()))
    assert r["replay_eligible"] is False
    assert "decision_path" in r["missing"]


def test_replay_ineligible_when_snapshot_reference_unresolvable():
    """正式 Gate（resolve_references=True）：引用必须可找回。"""
    r = replay_eligibility(
        _conn(), _snap(), resolve_references=True,
        resolvable_data_ids=set(), resolvable_universe_ids=set())
    assert r["replay_eligible"] is False
    assert "data_snapshot_id(UNRESOLVABLE)" in r["missing"]
    assert "universe_snapshot_id(UNRESOLVABLE)" in r["missing"]


def test_replay_eligible_when_snapshot_references_resolvable():
    r = replay_eligibility(
        _conn(), _snap(), resolve_references=True,
        resolvable_data_ids={"DS-1"},
        resolvable_universe_ids={"UV-1"})
    assert r["replay_eligible"] is True
