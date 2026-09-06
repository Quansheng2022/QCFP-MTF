# coding: utf-8
"""P5-D / WP5.1 — Shadow Isolation proof tests.

Threat model: prove isolation of the GOVERNED Phase 5 runtime surface.
Sandbox protection against arbitrary malicious Python / OS-level code is NOT
claimed here.

Proofs:
    * SHADOW / REPLAY / CANONICAL capture leave canonical authority unchanged
    * production/action mutator call count == 0
    * authority mutator call count == 0
    * generic CANONICAL/REPLAY bypass rejected
    * shadow storage cannot resolve into canonical storage
    * authority-looking shadow outputs remain non-authoritative data
"""

import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.phase5 import shadow_runtime as rt  # noqa: E402
from QCFP_MTF.phase5.shadow_isolation import (  # noqa: E402
    IsolationViolation,
    assert_authority_unchanged,
    assert_zero_calls,
    diff_snapshots,
    sha256_file,
    snapshot_canonical_db,
    snapshot_files,
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
        snapshot_canonical_db(root / "SQLiteDB" / "HK_Stock.db"),
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


@pytest.fixture
def store(tmp_path):
    return ShadowStore(tmp_path / "shadow_store")


@dataclass
class _FakeSnapshot:
    decision: str
    target: float


def _patch_canonical_engine(monkeypatch):
    calls: list[dict] = []

    def fake_engine_evaluate(
        evidence, previous_state, previous_position, settings,
        config=None, rule_version=None, model_version=None, run_id="",
        decision_id=None,
    ):
        calls.append(dict(evidence))
        return _FakeSnapshot(decision="CANONICAL", target=0.1)

    monkeypatch.setattr(
        "QCFP_MTF.decision.engine.evaluate", fake_engine_evaluate)
    return calls


def _install_spies(monkeypatch) -> dict:
    """Install counting spies over real authority/production mutator entries."""
    counters = {
        "authority_mutator_calls": 0,
        "production_action_calls": 0,
    }

    def spy_authority(*args, **kwargs):
        counters["authority_mutator_calls"] += 1
        raise AssertionError("SHADOW_AUTHORITY_PATH_VIOLATION")

    def spy_production(*args, **kwargs):
        counters["production_action_calls"] += 1
        raise AssertionError("SHADOW_PRODUCTION_PATH_VIOLATION")

    import QCFP_MTF.decision.decision_ledger as ledger
    import QCFP_MTF.decision.governance as governance
    import QCFP_MTF.decision.retail_position_fsm as rfsm
    import QCFP_MTF.execution.broker_adapter as broker
    import QCFP_MTF.execution.execution_gate as exec_gate
    import QCFP_MTF.execution.order_state_machine as osm
    import QCFP_MTF.governance.promotion_gate as prom_gate

    for module, name in (
        (ledger, "ledger_event"),
        (ledger, "record_snapshot"),
        (ledger, "register_model"),
        (governance, "finalize_target"),
        (rfsm, "transition"),
        (prom_gate, "promote_release_status"),
    ):
        monkeypatch.setattr(module, name, spy_authority)

    monkeypatch.setattr(exec_gate, "execute", spy_production)
    monkeypatch.setattr(broker.BrokerAdapter, "submit_order", spy_production)
    monkeypatch.setattr(osm.OrderStateMachine, "send", spy_production)
    return counters


@pytest.mark.parametrize(
    "mode",
    ["SHADOW", "REPLAY", "CANONICAL_CAPTURE"],
)
def test_cross_mode_authority_unchanged(store, tmp_path, monkeypatch, mode):
    _patch_canonical_engine(monkeypatch)
    counters = _install_spies(monkeypatch)
    files_before, db_before = _snapshot_authority(PROJECT_ROOT)

    if mode == "SHADOW":
        rt.ShadowRuntime(store, evaluator=_shadow_evaluator).execute(
            mode="SHADOW", input_payload={"symbol": "00700"},
            evaluation_timestamp=TS, **_identity_kwargs())
    elif mode == "REPLAY":
        runtime = rt.ShadowRuntime(store, evaluator=_shadow_evaluator)
        original = runtime.execute(
            mode="SHADOW", input_payload={"symbol": "00700"},
            evaluation_timestamp=TS, **_identity_kwargs())
        replay_shadow_run(
            store, original["shadow_run_id"], _shadow_evaluator,
            expected=_identity_kwargs(), evaluation_timestamp=TS)
    else:
        rt.ShadowRuntime(store, evaluator=_shadow_evaluator).capture_canonical(
            evidence={"close": 100.0},
            previous_state="HOLD",
            previous_position=0.0,
            settings={"quality": "OK"},
            run_id="RUN-1",
            evaluation_timestamp=TS,
            **_identity_kwargs(),
        )

    files_after, db_after = _snapshot_authority(PROJECT_ROOT)
    assert_authority_unchanged(files_before, files_after)
    assert diff_snapshots(db_before, db_after) == {
        "modified": [], "created": [], "deleted": [],
    }
    assert_zero_calls(counters["authority_mutator_calls"],
                      "authority mutator")
    assert_zero_calls(counters["production_action_calls"],
                      "production action")


def test_shadow_storage_cannot_resolve_into_canonical(tmp_path):
    direct = tmp_path / "SQLiteDB" / "shadow"
    with pytest.raises(Exception):
        ShadowStore(direct)
    alias = tmp_path / "x" / ".." / "SQLiteDB" / "shadow"
    with pytest.raises(Exception):
        ShadowStore(alias)
    with pytest.raises(IsolationViolation):
        validate_shadow_storage_boundary(direct)


def test_authority_like_shadow_output_is_non_authoritative(
    store, tmp_path, monkeypatch
):
    counters = _install_spies(monkeypatch)
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
    assert str(store.root) != str(PROJECT_ROOT / "SQLiteDB")
    files_after, db_after = _snapshot_authority(PROJECT_ROOT)
    assert_authority_unchanged(files_before, files_after)
    assert diff_snapshots(db_before, db_after) == {
        "modified": [], "created": [], "deleted": [],
    }
    assert_zero_calls(counters["authority_mutator_calls"],
                      "authority mutator")
    assert_zero_calls(counters["production_action_calls"],
                      "production action")


def test_generic_mode_bypass_still_rejected(store):
    runtime = rt.ShadowRuntime(store, evaluator=_shadow_evaluator)
    for mode in ("CANONICAL", "REPLAY"):
        with pytest.raises(rt.ShadowRuntimeError):
            runtime.execute(
                mode=mode, input_payload={"symbol": "00700"},
                evaluation_timestamp=TS, **_identity_kwargs())
    with pytest.raises(TypeError):
        runtime.capture_canonical(
            evidence={"close": 100.0}, previous_state="HOLD",
            previous_position=0.0, settings={},
            bridge=_shadow_evaluator, evaluation_timestamp=TS,
            **_identity_kwargs())


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
