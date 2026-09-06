# coding: utf-8
"""P5-C / WP5.1 — governed Shadow Runtime dedicated tests.

Covers: identity, runtime modes, independent storage, replay, and minimal
no-write-back guards. Systematic isolation proof belongs to P5-D.
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.phase5.contracts import (  # noqa: E402
    RUNTIME_MODES,
    validate_contract_dict,
)
from QCFP_MTF.phase5 import shadow_runtime as rt  # noqa: E402
from QCFP_MTF.phase5.shadow_store import ShadowStore  # noqa: E402
from QCFP_MTF.phase5.shadow_replay import (  # noqa: E402
    ReplayMismatch,
    replay_shadow_run,
)


TS = "2026-09-07T01:00:00Z"
AS_OF = "2026-09-06T00:00:00Z"


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


def _fake_evaluator(payload):
    return {
        "decision": "SHADOW",
        "symbol": payload.get("symbol", "00700"),
        "target": 0.1,
    }


@pytest.fixture
def store(tmp_path):
    return ShadowStore(tmp_path / "shadow_store")


def test_identity_deterministic_and_contract_valid():
    factory = rt.ShadowIdentityFactory()
    a = factory.generate(**_identity_kwargs(), runtime_mode="SHADOW",
                         evaluation_timestamp=TS)
    b = factory.generate(**_identity_kwargs(), runtime_mode="SHADOW",
                         evaluation_timestamp=TS)
    assert a == b
    validate_contract_dict(a)
    for field in (
        "shadow_run_id", "decision_id", "source_snapshot_id",
        "evidence_pack_id", "canonical_baseline_id", "shadow_version_id",
        "evaluation_timestamp", "as_of_timestamp", "runtime_mode",
        "config_hash", "code_identity",
    ):
        assert field in a


def test_identity_binding_change_changes_run_id():
    factory = rt.ShadowIdentityFactory()
    base = factory.generate(**_identity_kwargs(), evaluation_timestamp=TS)
    for field, value in (
        ("code_identity", "code-2"),
        ("config_hash", "cfg-2"),
        ("canonical_baseline_id", "BASE-2"),
    ):
        changed = factory.generate(
            **_identity_kwargs(**{field: value}),
            evaluation_timestamp=TS,
        )
        assert changed["shadow_run_id"] != base["shadow_run_id"]


def test_invalid_identity_rejected():
    factory = rt.ShadowIdentityFactory()
    with pytest.raises(Exception):
        factory.generate(
            **_identity_kwargs(config_hash=""), evaluation_timestamp=TS)
    with pytest.raises(TypeError):
        factory.generate(
            **_identity_kwargs(), evaluation_timestamp=TS,
            unexpected_field="x")


@pytest.mark.parametrize("mode", ["CANONICAL", "SHADOW", "REPLAY"])
def test_runtime_modes_accepted(mode):
    assert rt.validate_runtime_mode(mode) == mode
    assert mode in RUNTIME_MODES


@pytest.mark.parametrize("mode", ["EXECUTE", "PRODUCTION", "AUTO", "UNKNOWN"])
def test_runtime_modes_fail_closed(mode):
    with pytest.raises(rt.ShadowRuntimeError):
        rt.validate_runtime_mode(mode)


def test_execute_writes_independent_shadow_storage(store, tmp_path):
    runtime = rt.ShadowRuntime(store, evaluator=_fake_evaluator)
    result = runtime.execute(
        mode="SHADOW",
        input_payload={"symbol": "00700", "close": 100.0},
        evaluation_timestamp=TS,
        **_identity_kwargs(),
    )
    assert result["runtime_mode"] == "SHADOW"
    assert store.read(result["shadow_run_id"])["shadow_run_id"] == \
        result["shadow_run_id"]
    decision = store.read_decision(result["shadow_run_id"])
    assert decision["output"]["symbol"] == "00700"
    assert "SQLiteDB" not in str(store.root)
    # no files created outside the store root inside tmp_path
    outside = [
        p for p in tmp_path.rglob("*")
        if p.is_file() and store.root not in p.parents
    ]
    assert outside == []


def test_storage_deterministic(store):
    runtime = rt.ShadowRuntime(store, evaluator=_fake_evaluator)
    first = runtime.execute(
        mode="SHADOW", input_payload={"symbol": "00700"},
        evaluation_timestamp=TS, **_identity_kwargs())
    run_file = store.root / "runs" / f"{first['shadow_run_id']}.json"
    bytes_before = run_file.read_bytes()
    # identical input -> identical run id -> file bytes unchanged
    second = runtime.execute(
        mode="SHADOW", input_payload={"symbol": "00700"},
        evaluation_timestamp=TS, **_identity_kwargs())
    assert second["shadow_run_id"] == first["shadow_run_id"]
    assert run_file.read_bytes() == bytes_before


def test_duplicate_identical_write_is_idempotent(store):
    runtime = rt.ShadowRuntime(store, evaluator=_fake_evaluator)
    first = runtime.execute(
        mode="SHADOW", input_payload={"symbol": "00700"},
        evaluation_timestamp=TS, **_identity_kwargs())
    run_file = store.root / "runs" / f"{first['shadow_run_id']}.json"
    run_bytes = run_file.read_bytes()
    dec_file = store.root / "decisions" / f"{first['shadow_run_id']}.json"
    dec_bytes = dec_file.read_bytes()
    second = runtime.execute(
        mode="SHADOW", input_payload={"symbol": "00700"},
        evaluation_timestamp=TS, **_identity_kwargs())
    assert second["shadow_run_id"] == first["shadow_run_id"]
    assert run_file.read_bytes() == run_bytes
    assert dec_file.read_bytes() == dec_bytes


def test_same_identity_different_input_fails_closed(store):
    runtime = rt.ShadowRuntime(store, evaluator=_fake_evaluator)
    first = runtime.execute(
        mode="SHADOW", input_payload={"symbol": "00700"},
        evaluation_timestamp=TS, **_identity_kwargs())
    run_file = store.root / "runs" / f"{first['shadow_run_id']}.json"
    dec_file = store.root / "decisions" / f"{first['shadow_run_id']}.json"
    run_before = run_file.read_bytes()
    dec_before = dec_file.read_bytes()
    with pytest.raises(rt.ShadowRuntimeError):
        runtime.execute(
            mode="SHADOW", input_payload={"symbol": "00700", "x": 1},
            evaluation_timestamp=TS, **_identity_kwargs())
    assert run_file.read_bytes() == run_before
    assert dec_file.read_bytes() == dec_before


def test_same_identity_same_input_different_output_fails_closed(store):
    def evaluator_v2(payload):
        return {"decision": "SHADOW", "symbol": "00700", "target": 0.2}

    runtime = rt.ShadowRuntime(store, evaluator=_fake_evaluator)
    first = runtime.execute(
        mode="SHADOW", input_payload={"symbol": "00700"},
        evaluation_timestamp=TS, **_identity_kwargs())
    dec_file = store.root / "decisions" / f"{first['shadow_run_id']}.json"
    dec_before = dec_file.read_bytes()
    with pytest.raises(rt.ShadowRuntimeError):
        rt.ShadowRuntime(store, evaluator=evaluator_v2).execute(
            mode="SHADOW", input_payload={"symbol": "00700"},
            evaluation_timestamp=TS, **_identity_kwargs())
    assert dec_file.read_bytes() == dec_before


def test_generic_execute_canonical_rejected(store):
    runtime = rt.ShadowRuntime(store, evaluator=_fake_evaluator)
    with pytest.raises(rt.ShadowRuntimeError):
        runtime.execute(
            mode="CANONICAL", input_payload={"symbol": "00700"},
            evaluation_timestamp=TS, **_identity_kwargs())


def _approved_test_bridge(payload):
    return {"decision": "CANONICAL", "symbol": payload.get("symbol"),
            "target": 0.1}


_approved_test_bridge._approved_canonical_bridge = True  # type: ignore


def test_canonical_capture_requires_approved_bridge(store):
    runtime = rt.ShadowRuntime(store, evaluator=_fake_evaluator)
    with pytest.raises(rt.ShadowRuntimeError):
        runtime.capture_canonical(
            input_payload={"symbol": "00700"}, bridge=_fake_evaluator,
            evaluation_timestamp=TS, **_identity_kwargs())
    result = runtime.capture_canonical(
        input_payload={"symbol": "00700"}, bridge=_approved_test_bridge,
        evaluation_timestamp=TS, **_identity_kwargs())
    assert result["runtime_mode"] == "CANONICAL"
    record = store.read(result["shadow_run_id"])
    assert record["runtime_mode"] == "CANONICAL"


def test_replay_matches_and_creates_replay_run(store):
    runtime = rt.ShadowRuntime(store, evaluator=_fake_evaluator)
    original = runtime.execute(
        mode="SHADOW", input_payload={"symbol": "01951"},
        evaluation_timestamp=TS, **_identity_kwargs())
    result = replay_shadow_run(
        store, original["shadow_run_id"], _fake_evaluator,
        expected=_identity_kwargs(), evaluation_timestamp=TS)
    assert result["replay_result"] == "MATCH"
    assert result["runtime_mode"] == "REPLAY"
    assert len(store.list_runs()) == 2


def test_replay_requires_explicit_expected_identity(store):
    runtime = rt.ShadowRuntime(store, evaluator=_fake_evaluator)
    original = runtime.execute(
        mode="SHADOW", input_payload={"symbol": "00700"},
        evaluation_timestamp=TS, **_identity_kwargs())
    with pytest.raises(ReplayMismatch):
        replay_shadow_run(
            store, original["shadow_run_id"], _fake_evaluator,
            expected={}, evaluation_timestamp=TS)


@pytest.mark.parametrize(
    "field",
    [
        "source_snapshot_id", "canonical_baseline_id",
        "shadow_version_id", "config_hash", "code_identity",
        "as_of_timestamp",
    ],
)
def test_replay_missing_expected_field_fails(store, field):
    runtime = rt.ShadowRuntime(store, evaluator=_fake_evaluator)
    original = runtime.execute(
        mode="SHADOW", input_payload={"symbol": "00700"},
        evaluation_timestamp=TS, **_identity_kwargs())
    expected = _identity_kwargs()
    del expected[field]
    with pytest.raises(ReplayMismatch):
        replay_shadow_run(
            store, original["shadow_run_id"], _fake_evaluator,
            expected=expected, evaluation_timestamp=TS)


@pytest.mark.parametrize(
    "field,value",
    [
        ("canonical_baseline_id", "OTHER-BASE"),
        ("config_hash", "other-cfg"),
        ("code_identity", "other-code"),
        ("source_snapshot_id", "other-snap"),
        ("as_of_timestamp", "2099-01-01T00:00:00Z"),
    ],
)
def test_replay_identity_mismatch_fails_closed(store, field, value):
    runtime = rt.ShadowRuntime(store, evaluator=_fake_evaluator)
    original = runtime.execute(
        mode="SHADOW", input_payload={"symbol": "00700"},
        evaluation_timestamp=TS, **_identity_kwargs())
    expected = _identity_kwargs(**{field: value})
    with pytest.raises(ReplayMismatch):
        replay_shadow_run(
            store, original["shadow_run_id"], _fake_evaluator,
            expected=expected, evaluation_timestamp=TS)


def test_replay_missing_source_fails_closed(store):
    runtime = rt.ShadowRuntime(store, evaluator=_fake_evaluator)
    original = runtime.execute(
        mode="SHADOW", input_payload={"symbol": "00700"},
        evaluation_timestamp=TS, **_identity_kwargs())
    decision_path = store.root / "decisions" / \
        f"{original['shadow_run_id']}.json"
    import json

    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    del decision["input"]
    decision_path.write_text(
        rt.deterministic_dumps(decision), encoding="utf-8")
    with pytest.raises(ReplayMismatch):
        replay_shadow_run(
            store, original["shadow_run_id"], _fake_evaluator,
            expected=_identity_kwargs(), evaluation_timestamp=TS)


def test_replay_output_mismatch_fails_closed(store):
    runtime = rt.ShadowRuntime(store, evaluator=_fake_evaluator)
    original = runtime.execute(
        mode="SHADOW", input_payload={"symbol": "00700"},
        evaluation_timestamp=TS, **_identity_kwargs())
    decision_path = store.root / "decisions" / \
        f"{original['shadow_run_id']}.json"
    import json

    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    decision["output_sha256"] = "0" * 64
    decision_path.write_text(
        rt.deterministic_dumps(decision), encoding="utf-8")
    with pytest.raises(ReplayMismatch):
        replay_shadow_run(
            store, original["shadow_run_id"], _fake_evaluator,
            expected=_identity_kwargs(), evaluation_timestamp=TS)


def test_no_canonical_write_back_imports():
    sources = {
        "shadow_runtime": Path(
            PROJECT_ROOT / "Core/QCFP_MTF/phase5/shadow_runtime.py"
        ).read_text(encoding="utf-8"),
        "shadow_store": Path(
            PROJECT_ROOT / "Core/QCFP_MTF/phase5/shadow_store.py"
        ).read_text(encoding="utf-8"),
        "shadow_replay": Path(
            PROJECT_ROOT / "Core/QCFP_MTF/phase5/shadow_replay.py"
        ).read_text(encoding="utf-8"),
    }
    for name, source in sources.items():
        for forbidden in (
            "decision_ledger", "permission_policy", "retail_fsm",
            "execution", "broker",
        ):
            assert f"import {forbidden}" not in source, \
                f"{name} imports canonical writer {forbidden}"


def test_canonical_evaluation_bridge_is_read_only_surface():
    """Bridge references frozen engine.evaluate; no canonical writer imports."""
    source = Path(
        PROJECT_ROOT / "Core/QCFP_MTF/phase5/shadow_runtime.py"
    ).read_text(encoding="utf-8")
    assert "from QCFP_MTF.decision.engine import evaluate" in source
    for forbidden in ("decision_ledger", "permission_policy", "retail_fsm"):
        assert f"import {forbidden}" not in source
