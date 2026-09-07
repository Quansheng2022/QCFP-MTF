# coding: utf-8
"""P5-F / WP5.3 — append-only Outcome sidecar store dedicated tests."""

import copy
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.phase5 import outcome_observer as oo  # noqa: E402
from QCFP_MTF.phase5 import outcome_store as ost  # noqa: E402


def _weekdays(start: date, count: int) -> list[str]:
    dates = []
    cursor = start
    while len(dates) < count:
        if cursor.weekday() < 5:
            dates.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return dates


SESSIONS = _weekdays(date(2026, 8, 24), 25)
T0 = "2026-08-24"


def _avail(day: str) -> str:
    return f"{day}T09:00:00Z"


def _bar(day: str, close: float, high: float | None = None,
         low: float | None = None) -> dict:
    return {
        "date": day,
        "high": close * 1.01 if high is None else high,
        "low": close * 0.99 if low is None else low,
        "close": close,
        "available_at": _avail(day),
    }


def _decision(decision_id: str = "D-1", semantic: str = "ENTRY") -> dict:
    return {
        "decision_id": decision_id,
        "instrument_id": "00700",
        "as_of_date": T0,
        "decision_semantic": semantic,
    }


def _market(source: str = "SNAP-1", start: float = 100.0) -> oo.MarketDataSnapshot:
    bars = tuple(
        _bar(day, start * (1.0 + 0.01 * index))
        for index, day in enumerate(SESSIONS)
    )
    return oo.MarketDataSnapshot(
        instrument_id="00700",
        source_identity="HKEX-DAILY-1",
        snapshot_identity=source,
        price_basis="ADJUSTED",
        adjustment_policy="ADJ-POLICY-1",
        source_version="1.0",
        bars=bars,
    )


def _observed_record(source="SNAP-1"):
    return oo.evaluate_horizon(
        _decision(), 3,
        session_dates=SESSIONS, clock_ts=_avail("2026-08-27"),
        market_data=_market(source))


def test_store_write_create_and_duplicate_identical(tmp_path):
    store = ost.OutcomeStore(tmp_path)
    record = _observed_record()
    first = store.write(record)
    second = store.write(record)
    assert first["written"] is True
    assert second["written"] is False
    assert second["status"] == "DUPLICATE_IDENTICAL"
    assert len(list((tmp_path / "observations").glob("*.json"))) == 1


def test_store_duplicate_semantic_noop_when_timestamp_differs(tmp_path):
    store = ost.OutcomeStore(tmp_path)
    record = _observed_record()
    store.write(record)
    rerun = copy.deepcopy(record)
    rerun["observation_timestamp"] = "2026-08-27T12:00:00Z"
    rerun["evidence_hash"] = ost.observation_evidence_hash(rerun)
    meta = store.write(rerun)
    assert meta["written"] is False
    assert meta["status"] == "DUPLICATE_SEMANTIC_NOOP"


def test_store_rejects_divergent_rewrite_of_same_identity(tmp_path):
    store = ost.OutcomeStore(tmp_path)
    record = _observed_record()
    store.write(record)
    tampered = copy.deepcopy(record)
    tampered["future_return"] = 0.99
    tampered["contract"] = dict(record["contract"])
    tampered["contract"]["future_return"] = 0.99
    tampered["evidence_hash"] = ost.observation_evidence_hash(tampered)
    with pytest.raises(ost.OutcomeStoreError):
        store.write(tampered)
    # Original remains byte-identical and valid.
    stored = store.read(record["observation_id"])
    assert stored["future_return"] == record["future_return"]


def test_data_revision_appends_new_observation_never_overwrites(tmp_path):
    store = ost.OutcomeStore(tmp_path)
    v1 = _observed_record(source="SNAP-1")
    store.write(v1)
    v2 = _observed_record(source="SNAP-2")
    v2["supersedes"] = v1["observation_id"]
    v2["evidence_hash"] = ost.observation_evidence_hash(v2)
    store.write(v2)
    ids = store.list_observations(decision_id="D-1")
    assert len(ids) == 2
    assert v1["observation_id"] in ids
    assert v2["observation_id"] in ids
    # Both versions remain readable and independently hash-verifiable.
    stored_v1 = store.read(v1["observation_id"])
    stored_v2 = store.read(v2["observation_id"])
    assert stored_v1["outcome_status"] == "OBSERVED"
    assert stored_v2["supersedes"] == v1["observation_id"]


def test_observation_id_binds_full_replay_identity(tmp_path):
    store = ost.OutcomeStore(tmp_path)
    record = _observed_record(source="SNAP-1")
    seed = ost.observation_identity_seed(record)
    expected_id = ost.observation_id_from_seed(seed)
    assert record["observation_id"] == expected_id
    # Different snapshot identity -> different observation identity.
    other = _observed_record(source="SNAP-2")
    assert other["observation_id"] != record["observation_id"]


def test_unknown_field_rejected(tmp_path):
    record = _observed_record()
    record["sneaky"] = "x"
    with pytest.raises(ost.OutcomeStoreError):
        ost.validate_observation(record)


def test_evidence_hash_tamper_rejected(tmp_path):
    record = _observed_record()
    record["evidence_hash"] = "0" * 64
    with pytest.raises(ost.OutcomeStoreError):
        ost.validate_observation(record)


def test_nan_rejected(tmp_path):
    record = _observed_record()
    record["future_return"] = float("nan")
    with pytest.raises(ost.OutcomeStoreError):
        ost.validate_observation(record)


def test_bad_timestamp_rejected(tmp_path):
    record = _observed_record()
    record["observation_cutoff"] = "not-a-timestamp"
    with pytest.raises(ost.OutcomeStoreError):
        ost.validate_observation(record)


def test_contract_status_mapping(tmp_path):
    unavailable = oo.evaluate_horizon(
        _decision(), 1,
        session_dates=SESSIONS, clock_ts=_avail("2026-08-25"),
        market_data=oo.MarketDataSnapshot(
            instrument_id="00700",
            source_identity="HKEX-DAILY-1",
            snapshot_identity="SNAP-MISSING",
            price_basis="ADJUSTED",
            adjustment_policy="ADJ-POLICY-1",
            source_version="1.0",
            bars=(_bar(T0, 100.0),),  # no T+1 bar
        ))
    assert unavailable["outcome_status"] == "DATA_UNAVAILABLE"
    ost.validate_observation(unavailable)
    assert unavailable["contract"]["outcome_status"] == "MISSING_DATA"


def test_store_refuses_canonical_storage_root(tmp_path):
    canonical = tmp_path / "SQLiteDB"
    canonical.mkdir()
    with pytest.raises(ost.OutcomeStoreError):
        ost.OutcomeStore(canonical)


def test_store_missing_observation_fails_closed(tmp_path):
    store = ost.OutcomeStore(tmp_path)
    with pytest.raises(ost.OutcomeStoreError):
        store.read("does-not-exist")


def test_stored_file_is_deterministic_json(tmp_path):
    store = ost.OutcomeStore(tmp_path)
    record = _observed_record()
    store.write(record)
    path = (tmp_path / "observations" / f"{record['observation_id']}.json")
    text = path.read_text(encoding="utf-8")
    parsed = json.loads(text)
    assert parsed == record
