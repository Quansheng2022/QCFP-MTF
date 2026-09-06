# coding: utf-8
"""P5-D-R1 — Shadow Isolation proof tests (semantic repair).

Taxonomy:
    * Canonical Authority Computation via approved engine.evaluate bridge = ALLOWED
    * Authority Bypass (direct finalize_target/FSM/permission/promotion)     = FORBIDDEN
    * Canonical Mutation / persistence write                                 = FORBIDDEN
    * Production action (broker/execution/order)                             = FORBIDDEN

Threat model: GOVERNED_PHASE5_RUNTIME_SURFACE. Arbitrary malicious Python /
OS-level sandboxing is NOT claimed.
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS  # noqa: E402
from QCFP_MTF.phase5 import shadow_runtime as rt  # noqa: E402
from QCFP_MTF.phase5.shadow_isolation import (  # noqa: E402
    IsolationViolation,
    assert_authority_unchanged,
    assert_no_forbidden_imports,
    assert_zero_calls,
    diff_snapshots,
    snapshot_files,
    snapshot_sqlite_family,
    validate_shadow_storage_boundary,
)
from QCFP_MTF.phase5.shadow_store import ShadowStore  # noqa: E402
from QCFP_MTF.phase5.shadow_replay import (  # noqa: E402
    replay_shadow_run,
)


TS = "2026-09-07T01:00:00Z"
AS_OF = "2026-09-06T00:00:00Z"

AUTHORITY_FILE_ANCHORS = (
    "Core/QCFP_MTF/decision/engine.py",
    "Core/QCFP_MTF/decision/governance.py",
    "Core/QCFP_MTF/decision/governance_caps.py",
    "Core/QCFP_MTF/decision/path_hash.py",
    "Core/QCFP_MTF/decision/decision_ledger.py",
    "Core/QCFP_MTF/decision/permission_gate.py",
    "Core/QCFP_MTF/decision/permission_policy.py",
    "Core/QCFP_MTF/decision/institutional_permission.py",
    "Core/QCFP_MTF/decision/retail_fsm.py",
    "Core/QCFP_MTF/decision/retail_position_fsm.py",
    "Core/QCFP_MTF/decision/fsm_authority.py",
    "Core/QCFP_MTF/decision/canonical_action.py",
    "Core/QCFP_MTF/decision/versions.py",
    "audit/phase5/phase5_governance_baseline.json",
)

PHASE5_RUNTIME_FILES = (
    "Core/QCFP_MTF/phase5/shadow_runtime.py",
    "Core/QCFP_MTF/phase5/shadow_store.py",
    "Core/QCFP_MTF/phase5/shadow_replay.py",
    "Core/QCFP_MTF/phase5/shadow_isolation.py",
)


def _authority_surface(root: Path) -> list[str]:
    rels = list(AUTHORITY_FILE_ANCHORS)
    tactical = root / "Core/QCFP_MTF/tactical"
    if tactical.exists():
        rels += [
            str(p.relative_to(root)).replace("\\", "/")
            for p in sorted(tactical.rglob("*.py"))
        ]
    return rels


def _snapshot_authority(root: Path):
    return (
        snapshot_files(root, _authority_surface(root)),
        snapshot_sqlite_family(root / "SQLiteDB" / "HK_Stock.db"),
    )


def _identity_kwargs(**overrides):
    kwargs = {
        "decision_id": "D-1",
        "source_snapshot_id": "SNAP-1",
        "evidence_pack_id": "EP-1",
        "canonical_baseline_id": "BASE-1",
        "shadow_version_id": "SV-1",
        "config_hash": "cfg-1",
        "code_identity": "code-1",
        "as_of_timestamp": AS_OF,
    }
    kwargs.update(overrides)
    return kwargs


def _shadow_evaluator(payload):
    return {"decision": "SHADOW", "symbol": payload.get("symbol"),
            "target": 0.1}


def _canonical_row() -> dict:
    return {
        "stock_code": "T_ISO", "decision_date": "2026-08-21",
        "c_state": "C↑", "f_state": "F↑", "p_state": "P↑",
        "prev_f_state": "F↑", "monthly_behavior_state": "Improving",
        "tactical_signal": "Breakout", "daily_state": "DAILY_BREAKOUT",
        "risk_level": "Low", "des_score": 0, "wave_strength": 0.95,
        "chip_stability_confidence": "High", "data_quality": "B",
        "q_position_52w": 0.2,
    }


@pytest.fixture
def store(tmp_path):
    return ShadowStore(tmp_path / "shadow_store")


def _install_spies(monkeypatch, *, include_bypass=True) -> dict:
    counters = {
        "canonical_mutation_calls": 0,
        "production_action_calls": 0,
        "authority_bypass_calls": 0,
    }

    def make(key):
        def spy(*args, **kwargs):
            counters[key] += 1
            raise AssertionError(f"SHADOW_{key.upper()}_VIOLATION")
        return spy

    import QCFP_MTF.decision.decision_ledger as ledger
    import QCFP_MTF.execution.broker_adapter as broker
    import QCFP_MTF.execution.execution_gate as exec_gate
    import QCFP_MTF.execution.order_state_machine as osm

    for module, name in (
        (ledger, "ledger_event"),
        (ledger, "record_snapshot"),
        (ledger, "register_model"),
    ):
        monkeypatch.setattr(
            module, name, make("canonical_mutation_calls"))

    monkeypatch.setattr(
        exec_gate, "execute", make("production_action_calls"))
    monkeypatch.setattr(
        broker.BrokerAdapter, "submit_order",
        make("production_action_calls"))
    monkeypatch.setattr(
        osm.OrderStateMachine, "send", make("production_action_calls"))

    if include_bypass:
        import QCFP_MTF.decision.governance as governance
        import QCFP_MTF.decision.retail_position_fsm as rfsm
        import QCFP_MTF.governance.promotion_gate as prom_gate

        for module, name in (
            (governance, "finalize_target"),
            (rfsm, "transition"),
            (prom_gate, "promote_release_status"),
        ):
            monkeypatch.setattr(
                module, name, make("authority_bypass_calls"))
    return counters


def _assert_zero(counters: dict) -> None:
    assert_zero_calls(
        counters["canonical_mutation_calls"], "canonical mutation")
    assert_zero_calls(
        counters["production_action_calls"], "production action")
    assert_zero_calls(
        counters["authority_bypass_calls"], "authority bypass")


@pytest.mark.parametrize("mode", ["SHADOW", "REPLAY"])
def test_shadow_and_replay_isolated(store, monkeypatch, mode):
    counters = _install_spies(monkeypatch, include_bypass=True)
    files_before, db_before = _snapshot_authority(PROJECT_ROOT)
    runtime = rt.ShadowRuntime(store, evaluator=_shadow_evaluator)
    if mode == "SHADOW":
        runtime.execute(
            mode="SHADOW", input_payload={"symbol": "00700"},
            evaluation_timestamp=TS, **_identity_kwargs())
    else:
        original = runtime.execute(
            mode="SHADOW", input_payload={"symbol": "00700"},
            evaluation_timestamp=TS, **_identity_kwargs())
        replay_shadow_run(
            store, original["shadow_run_id"], _shadow_evaluator,
            expected=_identity_kwargs(), evaluation_timestamp=TS)
    files_after, db_after = _snapshot_authority(PROJECT_ROOT)
    assert_authority_unchanged(files_before, files_after)
    assert diff_snapshots(db_before, db_after) == {
        "modified": [], "created": [], "deleted": [],
    }
    _assert_zero(counters)


def test_canonical_capture_runs_real_engine_without_write_back(
    store, monkeypatch
):
    """CANONICAL capture executes the REAL decision.engine.evaluate (no fake)."""
    counters = _install_spies(monkeypatch, include_bypass=False)
    files_before, db_before = _snapshot_authority(PROJECT_ROOT)

    runtime = rt.ShadowRuntime(store, evaluator=_shadow_evaluator)
    result = runtime.capture_canonical(
        evidence=_canonical_row(),
        previous_state="FLAT",
        previous_position=0.0,
        settings=DEFAULT_SETTINGS,
        rule_version=None,
        model_version=None,
        run_id="ISO-RUN-1",
        evaluation_timestamp=TS,
        **_identity_kwargs(),
    )
    assert result["runtime_mode"] == "CANONICAL"
    decision = store.read_decision(result["shadow_run_id"])
    output = decision["output"]
    for field in (
        "decision_id", "stock_code", "decision_date",
        "institutional_permission", "next_fsm_state", "target_position",
        "decision_path",
    ):
        assert field in output, f"real canonical snapshot missing {field}"
    assert decision["input"]["run_id"] == "ISO-RUN-1"

    files_after, db_after = _snapshot_authority(PROJECT_ROOT)
    assert_authority_unchanged(files_before, files_after)
    assert diff_snapshots(db_before, db_after) == {
        "modified": [], "created": [], "deleted": [],
    }
    assert_zero_calls(
        counters["canonical_mutation_calls"], "canonical mutation")
    assert_zero_calls(
        counters["production_action_calls"], "production action")


def test_phase5_runtime_has_no_direct_authority_imports():
    assert_no_forbidden_imports(PROJECT_ROOT, PHASE5_RUNTIME_FILES)


def test_shadow_storage_cannot_resolve_into_canonical(tmp_path):
    direct = tmp_path / "SQLiteDB" / "shadow"
    alias = tmp_path / "x" / ".." / "SQLiteDB" / "shadow"
    for root in (direct, alias):
        with pytest.raises(Exception):
            ShadowStore(root)
        with pytest.raises(IsolationViolation):
            validate_shadow_storage_boundary(root)


def test_authority_like_shadow_output_is_non_authoritative(
    store, monkeypatch
):
    counters = _install_spies(monkeypatch, include_bypass=True)
    files_before, db_before = _snapshot_authority(PROJECT_ROOT)

    def authority_like_evaluator(payload):
        return {"decision": "APPROVE", "promote": True, "target": 1.0}

    runtime = rt.ShadowRuntime(store, evaluator=authority_like_evaluator)
    result = runtime.execute(
        mode="SHADOW", input_payload={"symbol": "00700"},
        evaluation_timestamp=TS, **_identity_kwargs())
    decision = store.read_decision(result["shadow_run_id"])
    assert decision["output"]["decision"] == "APPROVE"
    assert decision["output"]["promote"] is True

    files_after, db_after = _snapshot_authority(PROJECT_ROOT)
    assert_authority_unchanged(files_before, files_after)
    assert diff_snapshots(db_before, db_after) == {
        "modified": [], "created": [], "deleted": [],
    }
    _assert_zero(counters)


def test_generic_mode_bypass_still_rejected(store):
    runtime = rt.ShadowRuntime(store, evaluator=_shadow_evaluator)
    for mode in ("CANONICAL", "REPLAY"):
        with pytest.raises(rt.ShadowRuntimeError):
            runtime.execute(
                mode=mode, input_payload={"symbol": "00700"},
                evaluation_timestamp=TS, **_identity_kwargs())


def test_same_run_id_divergent_rewrite_still_fails_closed(store):
    runtime = rt.ShadowRuntime(store, evaluator=_shadow_evaluator)
    first = runtime.execute(
        mode="SHADOW", input_payload={"symbol": "00700"},
        evaluation_timestamp=TS, **_identity_kwargs())
    dec_path = store.root / "decisions" / f"{first['shadow_run_id']}.json"
    before = dec_path.read_bytes()
    with pytest.raises(rt.ShadowRuntimeError):
        rt.ShadowRuntime(store, evaluator=lambda p: {"target": 9.9}).execute(
            mode="SHADOW", input_payload={"symbol": "00700"},
            evaluation_timestamp=TS, **_identity_kwargs())
    assert dec_path.read_bytes() == before
