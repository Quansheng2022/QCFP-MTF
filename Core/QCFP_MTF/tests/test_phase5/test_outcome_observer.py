# coding: utf-8
"""P5-F / WP5.3 — Outcome Observer dedicated tests.

Covers the frozen hard invariants:
    * F-INV-01 Decision Immutability
    * F-INV-02 Future Only
    * F-INV-03 No Future Leakage
    * F-INV-04 Fixed Horizon
    * F-INV-05 Provenance Required
    * F-INV-06 Append-only Observation
    * F-INV-07 No Authority Feedback
    * F-INV-08 Deterministic Replay

Blocking tests (WP5.3 gate):
    BLOCKER-F01 future leakage
    BLOCKER-F02 historical Decision mutation
    BLOCKER-F03 horizon drift/substitution
    BLOCKER-F04 non-replayable Outcome
"""

import copy
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.phase5 import outcome_observer as oo  # noqa: E402


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
T1 = "2026-08-25"
T3 = "2026-08-27"
T5 = "2026-08-31"
T10 = "2026-09-07"
T20 = "2026-09-21"


def _avail(session_date: str) -> str:
    return f"{session_date}T09:00:00Z"


def _bar(session_date: str, close: float, *,
         high: float | None = None, low: float | None = None,
         available_at: str | None = None) -> dict:
    high = close * 1.01 if high is None else high
    low = close * 0.99 if low is None else low
    return {
        "date": session_date,
        "high": high,
        "low": low,
        "close": close,
        "available_at": available_at or _avail(session_date),
    }


def _market_bars(sessions, *, base=100.0, step=0.01,
                 start_price: dict | None = None) -> tuple[dict, ...]:
    bars = []
    for index, session_date in enumerate(sessions):
        if start_price is not None and session_date in start_price:
            close = float(start_price[session_date])
        else:
            close = base * (1.0 + step * index)
        bars.append(_bar(session_date, close))
    return tuple(bars)


def _decision(**overrides) -> dict:
    data = {
        "decision_id": "D-2026-08-24-00700",
        "instrument_id": "00700",
        "as_of_date": T0,
        "decision_semantic": "ENTRY",
    }
    data.update(overrides)
    return data


def _market(bars=None, *, source="SNAP-1", instrument="00700",
            price_basis="ADJUSTED") -> oo.MarketDataSnapshot:
    return oo.MarketDataSnapshot(
        instrument_id=instrument,
        source_identity="HKEX-DAILY-1",
        snapshot_identity=source,
        price_basis=price_basis,
        adjustment_policy="ADJ-POLICY-1",
        source_version="1.0",
        bars=tuple(bars) if bars is not None
        else _market_bars(SESSIONS),
    )


class RecordingMarket(oo.MarketDataSnapshot):
    """Market snapshot that records data access (leakage boundary spy)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.access_count = 0

    def visible(self, clock_ts: str):
        self.access_count += 1
        return super().visible(clock_ts)


# ---------------------------------------------------------------------------
# F-INV-04 Fixed horizon semantics
# ---------------------------------------------------------------------------

def test_exact_t_plus_one_resolution():
    resolved = oo.resolve_horizon_sessions(SESSIONS, T0)
    assert resolved[1].isoformat() == T1


def test_exact_t_plus_3_5_10_20_resolution():
    resolved = oo.resolve_horizon_sessions(SESSIONS, T0)
    assert resolved[3].isoformat() == T3
    assert resolved[5].isoformat() == T5
    assert resolved[10].isoformat() == T10
    assert resolved[20].isoformat() == T20


def test_same_day_is_never_a_horizon():
    resolved = oo.resolve_horizon_sessions(SESSIONS, T0)
    assert resolved[1] != date(2026, 8, 24)


def test_non_session_as_of_fails_closed():
    with pytest.raises(oo.OutcomeObservationError):
        oo.resolve_horizon_sessions(SESSIONS, "2026-08-23")  # Sunday


def test_horizon_beyond_calendar_never_shifts():
    short_sessions = _weekdays(date(2026, 8, 24), 12)
    resolved = oo.resolve_horizon_sessions(short_sessions, T0)
    assert resolved[10] is None or resolved[20] is None


# ---------------------------------------------------------------------------
# F-INV-02 / F-INV-03 future-only + no leakage
# ---------------------------------------------------------------------------

def _clock(day: str) -> str:
    return f"{day}T09:00:00Z"


def test_eligibility_requires_session_availability():
    assert not oo.horizon_eligible(
        "2026-08-25T08:59:59Z", T1)
    assert oo.horizon_eligible("2026-08-25T09:00:00Z", T1)


def test_future_injected_rows_are_not_visible():
    bars = list(_market_bars(SESSIONS))
    # Future T+5 row physically injected before its availability time.
    bars.append(_bar(T5, 999.0, available_at=_avail(T5)))
    visible = oo.visible_bars(bars, _clock(T3))
    assert T5 not in {bar["date"] for bar in visible}


def test_future_injected_rows_do_not_affect_due_horizon():
    bars = list(_market_bars(SESSIONS))
    bars.append(_bar(T5, 999.0, available_at=_avail(T5)))
    market = _market(bars)
    record = oo.evaluate_horizon(
        _decision(), 3,
        session_dates=SESSIONS, clock_ts=_clock(T3),
        market_data=market)
    assert record["outcome_status"] == "OBSERVED"
    assert record["horizon_price"] != 999.0


def test_not_due_horizon_never_touches_data_boundary():
    market = RecordingMarket(
        instrument_id="00700",
        source_identity="HKEX-DAILY-1",
        snapshot_identity="SNAP-1",
        price_basis="ADJUSTED",
        adjustment_policy="ADJ-POLICY-1",
        source_version="1.0",
        bars=_market_bars(SESSIONS),
    )
    record = oo.evaluate_horizon(
        _decision(), 5,
        session_dates=SESSIONS, clock_ts=_clock(T3),
        market_data=market)
    assert record["status"] == "NOT_DUE"
    assert market.access_count == 0


def test_observer_at_t3_sees_only_t1_and_t3():
    market = _market()
    result = oo.OutcomeObserver().observe(
        _decision(), session_dates=SESSIONS,
        clock_ts=_clock(T3), market_data=market)
    status_by_horizon = {
        item["horizon"]: item["status"] for item in result["results"]
    }
    assert status_by_horizon == {
        1: "OBSERVED", 3: "OBSERVED",
        5: "NOT_DUE", 10: "NOT_DUE", 20: "NOT_DUE",
    }


# ---------------------------------------------------------------------------
# Metric correctness (Return / MAE / MFE)
# ---------------------------------------------------------------------------

HAND_BARS = (
    _bar("2026-08-24", 100.0, high=101.0, low=99.0),
    _bar("2026-08-25", 102.0, high=103.0, low=101.0),
    _bar("2026-08-26", 97.0, high=104.0, low=96.0),
    _bar("2026-08-27", 96.0, high=98.0, low=95.0),
    _bar("2026-08-28", 95.0, high=97.0, low=94.0),
    _bar("2026-08-31", 94.0, high=99.0, low=93.0),
)


def _evaluate_hand(horizon: int, clock_day: str, **decision_overrides):
    return oo.evaluate_horizon(
        _decision(**decision_overrides), horizon,
        session_dates=SESSIONS, clock_ts=_clock(clock_day),
        market_data=_market(HAND_BARS))


def test_long_t_plus_1_metrics_hand_oracle():
    record = _evaluate_hand(1, "2026-08-25")
    assert record["outcome_status"] == "OBSERVED"
    assert record["reference_price"] == 100.0
    assert record["reference_price_source"] == "MARKET_T0"
    assert record["horizon_price"] == 102.0
    assert record["raw_return"] == pytest.approx(0.02)
    assert record["path_high"] == 103.0
    assert record["path_low"] == 101.0
    assert record["raw_max_excursion"] == pytest.approx(0.03)
    assert record["raw_min_excursion"] == pytest.approx(0.01)
    assert record["future_return"] == pytest.approx(0.02)
    assert record["directional_mfe"] == pytest.approx(0.03)
    assert record["directional_mae"] == pytest.approx(0.0)


def test_long_t_plus_3_metrics_hand_oracle():
    record = _evaluate_hand(3, "2026-08-27")
    assert record["horizon_price"] == 96.0
    assert record["raw_return"] == pytest.approx(-0.04)
    assert record["path_high"] == 104.0
    assert record["path_low"] == 95.0
    assert record["directional_mfe"] == pytest.approx(0.04)
    assert record["directional_mae"] == pytest.approx(0.05)


def test_long_t_plus_5_metrics_hand_oracle():
    record = _evaluate_hand(5, "2026-08-31")
    assert record["horizon_price"] == 94.0
    assert record["raw_return"] == pytest.approx(-0.06)
    assert record["directional_mfe"] == pytest.approx(0.04)
    assert record["directional_mae"] == pytest.approx(0.07)


def test_same_day_bars_are_excluded_from_path():
    bars = [
        _bar("2026-08-24", 100.0, high=999.0, low=1.0),
        _bar("2026-08-25", 102.0, high=103.0, low=101.0),
    ]
    record = oo.evaluate_horizon(
        _decision(), 1,
        session_dates=SESSIONS, clock_ts=_clock("2026-08-25"),
        market_data=_market(bars))
    assert record["path_high"] == 103.0
    assert record["path_low"] == 101.0


def test_short_metrics_via_explicit_policy():
    policy = oo.OutcomeInterpretationPolicy(
        version="TEST-SHORT-1",
        mapping={"SELL": "SHORT", "BUY": "LONG", "HOLD": "FLAT"},
    )
    record = oo.evaluate_horizon(
        _decision(decision_semantic="SELL"), 3,
        session_dates=SESSIONS, clock_ts=_clock(T3),
        market_data=_market(HAND_BARS),
        interpretation_policy=policy)
    assert record["direction_interpretation"] == "SHORT"
    assert record["future_return"] == pytest.approx(0.04)
    assert record["directional_mfe"] == pytest.approx(0.05)
    assert record["directional_mae"] == pytest.approx(0.04)


def test_flat_semantics_record_raw_facts_without_direction():
    record = oo.evaluate_horizon(
        _decision(decision_semantic="NO_TRADE"), 3,
        session_dates=SESSIONS, clock_ts=_clock(T3),
        market_data=_market(HAND_BARS))
    assert record["outcome_status"] == "OBSERVED"
    assert record["direction_interpretation"] == "FLAT"
    assert record["raw_return"] is not None
    assert record["future_return"] is None
    assert record["directional_mfe"] is None
    assert record["directional_mae"] is None
    assert record["contract"]["outcome_status"] == "REALIZED"


def test_unknown_decision_semantic_fails_closed():
    policy = oo.OutcomeInterpretationPolicy(mapping={"BUY": "LONG"})
    with pytest.raises(oo.OutcomeObservationError):
        oo.OutcomeInterpretationPolicy().interpret("BUY")
    with pytest.raises(oo.OutcomeObservationError):
        oo.evaluate_horizon(
            _decision(decision_semantic="MYSTERY"), 1,
            session_dates=SESSIONS, clock_ts=_clock(T1),
            market_data=_market(HAND_BARS),
            interpretation_policy=policy)


# ---------------------------------------------------------------------------
# F-INV-04 / BLOCKER-F03 suspension & missing data
# ---------------------------------------------------------------------------

def test_suspension_never_shifts_horizon():
    # Sessions T+1 and T+2 have no instrument bar (suspended); T+3 resumed.
    bars = [
        _bar(T0, 100.0),
        _bar(T3, 96.0, high=98.0, low=95.0),
    ]
    market = _market(bars)
    rec1 = oo.evaluate_horizon(
        _decision(), 1, session_dates=SESSIONS,
        clock_ts=_clock(T3), market_data=market)
    rec3 = oo.evaluate_horizon(
        _decision(), 3, session_dates=SESSIONS,
        clock_ts=_clock(T3), market_data=market)
    assert rec1["outcome_status"] == "DATA_UNAVAILABLE"
    assert rec1["reason"].startswith("instrument has no bar")
    assert rec1["reason_code"] == "NO_BAR_FOR_HORIZON_SESSION"
    assert rec3["outcome_status"] == "OBSERVED"
    assert rec3["horizon_price"] == 96.0


def test_no_forward_fill_or_carry_forward():
    bars = [_bar(T0, 100.0), _bar(T3, 96.0)]
    market = _market(bars)
    rec1 = oo.evaluate_horizon(
        _decision(), 1, session_dates=SESSIONS,
        clock_ts=_clock(T3), market_data=market)
    assert rec1["outcome_status"] == "DATA_UNAVAILABLE"
    assert rec1["horizon_price"] is None


def test_missing_horizon_session_becomes_unavailable():
    short_sessions = _weekdays(date(2026, 8, 24), 8)
    market = _market(_market_bars(short_sessions))
    record = oo.evaluate_horizon(
        _decision(), 20, session_dates=short_sessions,
        clock_ts="2026-12-31T09:00:00Z", market_data=market)
    assert record["outcome_status"] == "DATA_UNAVAILABLE"
    assert record["reason"].startswith("exchange calendar")
    assert record["reason_code"] == "CALENDAR_INSUFFICIENT"


def test_missing_horizon_before_last_known_session_is_not_due():
    short_sessions = _weekdays(date(2026, 8, 24), 8)
    market = _market(_market_bars(short_sessions))
    record = oo.evaluate_horizon(
        _decision(), 20, session_dates=short_sessions,
        clock_ts=_clock("2026-08-25"), market_data=market)
    assert record["status"] == "NOT_DUE"


# ---------------------------------------------------------------------------
# F-INV-01 / BLOCKER-F02 Decision immutability & no authority feedback
# ---------------------------------------------------------------------------

def test_decision_hash_identical_before_and_after_observation():
    view = _decision()
    before = oo.canonical_decision_hash(view)
    view_copy = copy.deepcopy(view)
    oo.OutcomeObserver().observe(
        view_copy, session_dates=SESSIONS,
        clock_ts=_clock(T20), market_data=_market())
    assert oo.canonical_decision_hash(view_copy) == before
    assert view_copy == view


def test_observer_never_mutates_decision_view():
    view = _decision()
    market = _market(HAND_BARS)
    oo.OutcomeObserver().observe(
        view, session_dates=SESSIONS,
        clock_ts=_clock(T3), market_data=market)
    assert view == _decision()


def test_observation_writes_only_to_outcome_store(tmp_path):
    from QCFP_MTF.phase5.outcome_store import OutcomeStore

    store = OutcomeStore(tmp_path)
    observer = oo.OutcomeObserver(store=store)
    observer.observe(
        _decision(), session_dates=SESSIONS,
        clock_ts=_clock(T3), market_data=_market(HAND_BARS))
    files = list((tmp_path / "observations").glob("*.json"))
    assert len(files) == 2  # T+1 and T+3 only


def test_contract_frozen_statuses_never_use_aging_vocabulary():
    record = _evaluate_hand(1, T1)
    assert record["contract"]["outcome_status"] == "REALIZED"
    assert "FRESH" not in record["contract"]["outcome_status"]
    assert "EXPIRED" not in record["contract"]["outcome_status"]


# ---------------------------------------------------------------------------
# F-INV-05 provenance / fail-closed inputs
# ---------------------------------------------------------------------------

def test_malformed_decision_identity_fails_closed():
    for overrides in (
        {"decision_id": ""},
        {"instrument_id": None},
        {"as_of_date": "not-a-date"},
        {"as_of_date": "2026-08-23"},
    ):
        with pytest.raises(oo.OutcomeObservationError):
            oo.evaluate_horizon(
                _decision(**overrides), 1,
                session_dates=SESSIONS, clock_ts=_clock(T1),
                market_data=_market())


def test_decision_hash_tamper_fails_closed():
    view = _decision(decision_hash="deadbeef")
    with pytest.raises(oo.OutcomeObservationError):
        oo.validate_decision_view(view)


def test_unknown_source_identity_fails_closed():
    with pytest.raises(oo.OutcomeObservationError):
        oo.MarketDataSnapshot(
            instrument_id="00700", source_identity="",
            snapshot_identity="SNAP-1", price_basis="ADJUSTED",
            adjustment_policy="ADJ-POLICY-1", source_version="1.0",
            bars=())


def test_unknown_price_basis_fails_closed():
    with pytest.raises(oo.OutcomeObservationError):
        oo.MarketDataSnapshot(
            instrument_id="00700", source_identity="SRC",
            snapshot_identity="SNAP-1", price_basis="RAW",
            adjustment_policy="ADJ-POLICY-1", source_version="1.0",
            bars=())


def test_instrument_mismatch_fails_closed():
    record = oo.evaluate_horizon(
        _decision(), 1, session_dates=SESSIONS,
        clock_ts=_clock(T1), market_data=_market(instrument="09999"))
    assert record["outcome_status"] == "OBSERVATION_ERROR"
    assert "instrument" in record["reason"].lower()
    assert record["reason_code"] == "INSTRUMENT_MISMATCH"


def test_price_basis_mismatch_fails_closed():
    bars = list(HAND_BARS)
    record = oo.evaluate_horizon(
        _decision(reference_price=105.0), 1,
        session_dates=SESSIONS, clock_ts=_clock(T1),
        market_data=_market(bars))
    assert record["outcome_status"] == "OBSERVATION_ERROR"
    assert "price basis" in record["reason"].lower()
    assert record["reason_code"] == "PRICE_BASIS_MISMATCH"


def test_matching_decision_reference_price_is_used():
    record = oo.evaluate_horizon(
        _decision(reference_price=100.0), 1,
        session_dates=SESSIONS, clock_ts=_clock(T1),
        market_data=_market(HAND_BARS))
    assert record["outcome_status"] == "OBSERVED"
    assert record["reference_price_source"] == "DECISION"
    assert record["reference_price"] == 100.0


# ---------------------------------------------------------------------------
# F-INV-08 / BLOCKER-F04 deterministic replay
# ---------------------------------------------------------------------------

def test_evaluate_is_deterministic():
    first = oo.evaluate_horizon(
        _decision(), 3, session_dates=SESSIONS,
        clock_ts=_clock(T3), market_data=_market(HAND_BARS))
    second = oo.evaluate_horizon(
        _decision(), 3, session_dates=SESSIONS,
        clock_ts=_clock(T3), market_data=_market(HAND_BARS))
    assert first == second


def test_replay_match(tmp_path):
    from QCFP_MTF.phase5.outcome_store import OutcomeStore

    store = OutcomeStore(tmp_path)
    record = oo.evaluate_horizon(
        _decision(), 3, session_dates=SESSIONS,
        clock_ts=_clock(T3), market_data=_market(HAND_BARS))
    store.write(record)
    stored = store.read(record["observation_id"])
    replay = oo.replay_observation(
        _decision(), horizon=3, session_dates=SESSIONS,
        clock_ts=_clock(T3), market_data=_market(HAND_BARS),
        stored_record=stored)
    assert replay["replay_status"] == "MATCH"


def test_replay_with_revised_snapshot_mismatches(tmp_path):
    from QCFP_MTF.phase5.outcome_store import OutcomeStore

    store = OutcomeStore(tmp_path)
    record = oo.evaluate_horizon(
        _decision(), 3, session_dates=SESSIONS,
        clock_ts=_clock(T3), market_data=_market(HAND_BARS))
    store.write(record)
    stored = store.read(record["observation_id"])
    revised_bars = tuple(
        _bar(bar["date"], float(bar["close"]) * 1.05)
        for bar in HAND_BARS
    )
    with pytest.raises(oo.OutcomeReplayMismatch):
        oo.replay_observation(
            _decision(), horizon=3, session_dates=SESSIONS,
            clock_ts=_clock(T3), market_data=_market(
                revised_bars, source="SNAP-2"),
            stored_record=stored)


def test_mfe_mae_deterministic():
    records = [
        oo.evaluate_horizon(
            _decision(), 5, session_dates=SESSIONS,
            clock_ts=_clock(T5), market_data=_market(HAND_BARS))
        for _ in range(2)
    ]
    assert records[0]["directional_mfe"] == records[1]["directional_mfe"]
    assert records[0]["directional_mae"] == records[1]["directional_mae"]
    assert records[0]["evidence_hash"] == records[1]["evidence_hash"]
