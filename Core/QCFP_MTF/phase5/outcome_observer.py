# coding: utf-8
"""P5-F / WP5.3 — Decision Outcome Observation (Outcome Observer).

The observer observes what happened *after* a Decision; it never changes what
the Decision was.  It is an Evidence Plane, not a Decision Plane:

    * T+1 / T+3 / T+5 / T+10 / T+20 resolved on an Exchange Trading Calendar
      (session N after the Decision Effective Session T0; never shifted)
    * future-only inputs: eligibility is clock based; the data-access boundary
      filters by availability and the engine only reads the resolved session
    * Return / MAE / MFE are deterministic, provenance-bound raw + directional
      metrics; raw excursions and directional interpretation are stored apart
    * observations are independent, append-only sidecar evidence (outcome_store)
    * zero write path into Decision / Permission / FSM / finalize_target

Phase boundary discipline:
    * minimal lifecycle only: NOT_DUE / ELIGIBLE / OBSERVED /
      DATA_UNAVAILABLE / OBSERVATION_ERROR
    * FRESH / AGING / STALE / EXPIRED / INVALID belongs to P5-G (not here)
    * incident severities / F1-F12 belongs to P5-H (not here)
    * no promotion / qualification authority (P5-I / P5-K, not here)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Mapping, Sequence

from .contracts import OutcomeContract, contract_dict
from .outcome_store import (
    CONTRACT_STATUS_MAP,
    OBSERVATION_SCHEMA,
    DIRECTIONS,
    observation_evidence_hash,
    observation_id_from_seed,
    observation_identity_seed,
)
from .shadow_runtime import deterministic_dumps


class OutcomeObservationError(RuntimeError):
    """Fail-closed outcome observer error (malformed/contradictory inputs)."""


class OutcomeReplayMismatch(OutcomeObservationError):
    """Replay mismatch; original observation stays authoritative."""


# ---------------------------------------------------------------------------
# Frozen policy vocabulary (WP5.3)
# ---------------------------------------------------------------------------

OUTCOME_HORIZONS = (1, 3, 5, 10, 20)
HORIZON_POLICY_VERSION = "HORIZON-T1-T3-T5-T10-T20-1"
OBSERVER_POLICY_VERSION = "P5-F-OUTCOME-OBSERVER-1"
METRIC_VERSION = "RETURN-MAE-MFE-1"

# Minimal observer lifecycle (see module docstring for boundaries).
OBSERVER_STATUSES = (
    "NOT_DUE", "ELIGIBLE", "OBSERVED",
    "DATA_UNAVAILABLE", "OBSERVATION_ERROR",
)
TERMINAL_STATUSES = ("OBSERVED", "DATA_UNAVAILABLE", "OBSERVATION_ERROR")

DECISION_HASH_FIELDS = (
    "decision_id", "instrument_id", "as_of_date", "decision_semantic",
)

OBSERVED_REASON_CODES = {
    "CALENDAR_INSUFFICIENT": (
        "exchange calendar does not contain the horizon session; "
        "no shift / no substitution"),
    "REFERENCE_PRICE_UNAVAILABLE": (
        "T0 reference bar unavailable at observation cutoff"),
    "NO_BAR_FOR_HORIZON_SESSION": (
        "instrument has no bar for the resolved horizon session; "
        "no forward-fill"),
    "PRICE_BASIS_MISMATCH": (
        "decision reference price does not match market-data T0 close on "
        "the declared price basis; fail closed, no auto conversion"),
    "INSTRUMENT_MISMATCH": (
        "market-data instrument identity does not match decision"),
    "MALFORMED_INPUT": "malformed decision/market input -> fail closed",
}

DEFAULT_INTERPRETATION_MAPPING = {
    # Repository canonical-action vocabulary (long-only semantics). The map is
    # explicit and versioned; the observer never infers a direction itself.
    "ENTRY": "LONG",
    "ADD": "LONG",
    "HOLD": "LONG",
    "REDUCE": "FLAT",
    "EXIT": "FLAT",
    "NO_TRADE": "FLAT",
}


@dataclass(frozen=True)
class OutcomeInterpretationPolicy:
    """Versioned mapping of an existing Decision semantic to interpretation.

    Unknown semantics fail closed: they must be registered in a new policy
    version instead of being silently guessed by the observer.
    """

    version: str = "QCFP-CANONICAL-ACTION-1"
    mapping: Mapping[str, str] = field(
        default_factory=lambda: dict(DEFAULT_INTERPRETATION_MAPPING))

    def interpret(self, decision_semantic: str) -> str:
        if not isinstance(decision_semantic, str) \
                or decision_semantic.strip() == "":
            raise OutcomeObservationError(
                "decision_semantic must be a non-empty string"
            )
        direction = self.mapping.get(decision_semantic)
        if direction is None:
            raise OutcomeObservationError(
                f"decision_semantic {decision_semantic!r} is not covered by "
                f"interpretation policy {self.version}; outcome "
                "interpretation must be explicit"
            )
        if direction not in DIRECTIONS:
            raise OutcomeObservationError(
                f"interpretation policy maps {decision_semantic!r} to "
                f"unsupported direction {direction!r}"
            )
        return direction


@dataclass(frozen=True)
class HorizonPolicy:
    """Deterministic exchange-session horizon semantics (WP5.3)."""

    version: str = HORIZON_POLICY_VERSION
    horizons: Sequence[int] = OUTCOME_HORIZONS
    session_close_hour_utc: int = 8   # HKEX close 16:00 HKT == 08:00 UTC
    publication_delay_hours: float = 1.0

    def availability_timestamp(self, session_date) -> str:
        d = _to_date(session_date)
        base = datetime(d.year, d.month, d.day,
                        self.session_close_hour_utc, 0, 0)
        available = base + timedelta(hours=self.publication_delay_hours)
        return available.strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class MarketDataSnapshot:
    """Bars + market-data provenance bound to one instrument."""

    instrument_id: str
    source_identity: str
    snapshot_identity: str
    price_basis: str
    adjustment_policy: str
    source_version: str
    bars: tuple[Mapping[str, Any], ...] = ()

    def __post_init__(self) -> None:
        for key in ("instrument_id", "source_identity",
                    "snapshot_identity", "price_basis",
                    "adjustment_policy", "source_version"):
            value = getattr(self, key)
            if not isinstance(value, str) or value.strip() == "":
                raise OutcomeObservationError(
                    f"market_data.{key} must be non-empty string"
                )
        if self.price_basis not in ("ADJUSTED", "UNADJUSTED"):
            raise OutcomeObservationError(
                f"unsupported price_basis {self.price_basis!r}"
            )

    def visible(self, clock_ts: str) -> tuple[dict[str, Any], ...]:
        """Data-access boundary: only rows available at or before the clock."""
        return tuple(_visible_bars(self.bars, clock_ts))


# ---------------------------------------------------------------------------
# Small deterministic helpers
# ---------------------------------------------------------------------------

def _to_date(value) -> Any:
    if isinstance(value, datetime):
        return value.date()
    if hasattr(value, "year") and hasattr(value, "month") \
            and hasattr(value, "day"):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def _parse_utc(value: str) -> datetime:
    if not isinstance(value, str):
        raise OutcomeObservationError(
            f"clock must be a UTC string, got {value!r}"
        )
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise OutcomeObservationError(
            f"invalid UTC timestamp {value!r}"
        ) from exc


def _finite(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        import math

        return math.isfinite(value)
    return False


def _round(value: float) -> float:
    return round(float(value), 10)


def _validate_bar(bar: Mapping[str, Any], index: int) -> dict[str, Any]:
    if not isinstance(bar, Mapping):
        raise OutcomeObservationError(f"bar[{index}] must be a mapping")
    required = ("date", "high", "low", "close", "available_at")
    missing = [key for key in required if bar.get(key) is None]
    if missing:
        raise OutcomeObservationError(
            f"bar[{index}] missing required field(s): {missing}"
        )
    date_text = str(bar["date"])
    try:
        datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError as exc:
        raise OutcomeObservationError(
            f"bar[{index}] invalid date {date_text!r}"
        ) from exc
    for key in ("high", "low", "close"):
        if not _finite(bar.get(key)):
            raise OutcomeObservationError(
                f"bar[{index}].{key} must be finite number"
            )
    try:
        datetime.strptime(str(bar["available_at"]), "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise OutcomeObservationError(
            f"bar[{index}] invalid available_at {bar['available_at']!r}"
        ) from exc
    return {
        "date": date_text,
        "high": float(bar["high"]),
        "low": float(bar["low"]),
        "close": float(bar["close"]),
        "available_at": str(bar["available_at"]),
    }


def visible_bars(
    bars: Sequence[Mapping[str, Any]],
    clock_ts: str,
) -> list[dict[str, Any]]:
    """Availability-time filtering (event time != availability time)."""
    clock = _parse_utc(clock_ts)
    out: list[dict[str, Any]] = []
    for index, bar in enumerate(bars):
        normalized = _validate_bar(bar, index)
        if _parse_utc(normalized["available_at"]) <= clock:
            out.append(normalized)
    out.sort(key=lambda item: item["date"])
    return out


def _visible_bars(
    bars: Sequence[Mapping[str, Any]],
    clock_ts: str,
) -> list[dict[str, Any]]:
    return visible_bars(bars, clock_ts)


# ---------------------------------------------------------------------------
# Decision view / canonical hash
# ---------------------------------------------------------------------------

def canonical_decision_hash(decision_view: Mapping[str, Any]) -> str:
    protected = {
        key: decision_view.get(key)
        for key in DECISION_HASH_FIELDS
        if decision_view.get(key) is not None
    }
    return _sha256_text(deterministic_dumps(protected))


def _sha256_text(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def validate_decision_view(decision_view: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(decision_view, Mapping):
        raise OutcomeObservationError("decision view must be a mapping")
    view = dict(decision_view)
    for key in ("decision_id", "instrument_id", "as_of_date",
                "decision_semantic"):
        value = view.get(key)
        if not isinstance(value, str) or value.strip() == "":
            raise OutcomeObservationError(
                f"decision view missing required {key}"
            )
    try:
        datetime.strptime(view["as_of_date"], "%Y-%m-%d")
    except (TypeError, ValueError) as exc:
        raise OutcomeObservationError(
            f"invalid as_of_date {view['as_of_date']!r}"
        ) from exc
    if "reference_price" in view and view["reference_price"] is not None:
        if not _finite(view["reference_price"]) \
                or float(view["reference_price"]) <= 0:
            raise OutcomeObservationError(
                "decision reference_price must be a positive finite number"
            )
    if "decision_hash" in view and view["decision_hash"] is not None:
        if not isinstance(view["decision_hash"], str) \
                or view["decision_hash"] != canonical_decision_hash(view):
            raise OutcomeObservationError(
                "decision_hash does not match the protected decision payload"
            )
    view["decision_hash"] = view.get("decision_hash") \
        or canonical_decision_hash(view)
    return view


# ---------------------------------------------------------------------------
# Horizon resolution / eligibility
# ---------------------------------------------------------------------------

def resolve_horizon_sessions(
    session_dates: Sequence[Any],
    as_of_date: Any,
    horizon_policy: HorizonPolicy | None = None,
) -> dict[int, Any | None]:
    """T+n = the n-th exchange session strictly after the T0 session."""
    policy = horizon_policy or HorizonPolicy()
    dates = sorted({_to_date(value) for value in session_dates})
    if not dates:
        raise OutcomeObservationError("session calendar is empty")
    as_of = _to_date(as_of_date)
    if as_of not in dates:
        raise OutcomeObservationError(
            f"as_of_date {as_of.isoformat()} is not an exchange session "
            "(Decision Effective Session must be a trading session)"
        )
    index = dates.index(as_of)
    resolved: dict[int, Any | None] = {}
    for horizon in policy.horizons:
        if not isinstance(horizon, int) or isinstance(horizon, bool) \
                or horizon <= 0:
            raise OutcomeObservationError(
                f"invalid horizon {horizon!r} in policy {policy.version}"
            )
        position = index + horizon
        resolved[horizon] = dates[position] if position < len(dates) else None
    return resolved


def horizon_eligible(
    clock_ts: str,
    session_date: Any,
    horizon_policy: HorizonPolicy | None = None,
) -> bool:
    policy = horizon_policy or HorizonPolicy()
    return _parse_utc(clock_ts) >= _parse_utc(
        policy.availability_timestamp(session_date))


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def directional_metrics(
    direction: str,
    raw_return: float,
    raw_max_excursion: float,
    raw_min_excursion: float,
) -> dict[str, float | None]:
    """Directional interpretation of raw market facts (never re-infers)."""
    if direction == "LONG":
        return {
            "future_return": _round(raw_return),
            "directional_mfe": _round(max(0.0, raw_max_excursion)),
            "directional_mae": _round(max(0.0, -raw_min_excursion)),
        }
    if direction == "SHORT":
        return {
            "future_return": _round(-raw_return),
            "directional_mfe": _round(max(0.0, -raw_min_excursion)),
            "directional_mae": _round(max(0.0, raw_max_excursion)),
        }
    # FLAT / NONE: raw path facts only; no directional claim.
    return {
        "future_return": None,
        "directional_mfe": None,
        "directional_mae": None,
    }


def _raw_metrics(
    reference_price: float,
    window_bars: Sequence[Mapping[str, Any]],
    horizon_price: float,
) -> dict[str, float]:
    path_high = max(float(bar["high"]) for bar in window_bars)
    path_low = min(float(bar["low"]) for bar in window_bars)
    raw_return = horizon_price / reference_price - 1.0
    raw_max_excursion = path_high / reference_price - 1.0
    raw_min_excursion = path_low / reference_price - 1.0
    return {
        "horizon_price": _round(horizon_price),
        "path_high": _round(path_high),
        "path_low": _round(path_low),
        "raw_return": _round(raw_return),
        "raw_max_excursion": _round(raw_max_excursion),
        "raw_min_excursion": _round(raw_min_excursion),
    }


def _build_contract(
    decision_view: Mapping[str, Any],
    horizon: int,
    outcome_status: str,
    observation_timestamp: str,
    future_return: float | None,
    mae: float | None,
    mfe: float | None,
) -> dict[str, Any]:
    contract_status = CONTRACT_STATUS_MAP[outcome_status]
    carrier = OutcomeContract(
        decision_id=decision_view["decision_id"],
        as_of_timestamp=f"{decision_view['as_of_date']}T00:00:00Z",
        observation_timestamp=observation_timestamp,
        horizon=horizon,
        outcome_status=contract_status,
        future_return=future_return,
        mae=mae,
        mfe=mfe,
    )
    return contract_dict(carrier)


# ---------------------------------------------------------------------------
# Single-horizon evaluation
# ---------------------------------------------------------------------------

def evaluate_horizon(
    decision_view: Mapping[str, Any],
    horizon: int,
    *,
    session_dates: Sequence[Any],
    clock_ts: str,
    market_data: MarketDataSnapshot,
    interpretation_policy: OutcomeInterpretationPolicy | None = None,
    horizon_policy: HorizonPolicy | None = None,
    observation_timestamp: str | None = None,
) -> dict[str, Any]:
    """Evaluate one horizon with strict future-only, fail-closed semantics.

    Returns a canonical observation record for terminal statuses
    (OBSERVED / DATA_UNAVAILABLE / OBSERVATION_ERROR) or a lightweight
    NOT_DUE status report (never persisted).
    """
    view = validate_decision_view(decision_view)
    ipolicy = interpretation_policy or OutcomeInterpretationPolicy()
    hpolicy = horizon_policy or HorizonPolicy()
    clock = _parse_utc(clock_ts)
    observed_at = observation_timestamp or clock_ts
    cutoff = clock_ts

    direction = ipolicy.interpret(view["decision_semantic"])
    resolved = resolve_horizon_sessions(
        session_dates, view["as_of_date"], horizon_policy=hpolicy)
    session = resolved.get(horizon)

    identity = {
        "decision_id": view["decision_id"],
        "decision_hash": view["decision_hash"],
        "instrument_id": view["instrument_id"],
        "horizon": horizon,
        "horizon_policy_version": hpolicy.version,
        "metric_version": METRIC_VERSION,
        "interpretation_policy_version": ipolicy.version,
        "policy_version": OBSERVER_POLICY_VERSION,
        "market_data_source_identity": market_data.source_identity,
        "market_data_snapshot_identity": market_data.snapshot_identity,
        "observation_cutoff": cutoff,
    }
    observation_id = observation_id_from_seed(identity)
    common = {
        "schema": OBSERVATION_SCHEMA,
        "observation_id": observation_id,
        "decision_id": view["decision_id"],
        "instrument_id": view["instrument_id"],
        "horizon": horizon,
        "observation_timestamp": observed_at,
        "observation_cutoff": cutoff,
        "policy_version": OBSERVER_POLICY_VERSION,
        "horizon_policy_version": hpolicy.version,
        "metric_version": METRIC_VERSION,
        "interpretation_policy_version": ipolicy.version,
        "direction_interpretation": direction,
        "decision_hash": view["decision_hash"],
        "market_data_source_identity": market_data.source_identity,
        "market_data_snapshot_identity": market_data.snapshot_identity,
        "price_basis": market_data.price_basis,
        "adjustment_policy": market_data.adjustment_policy,
        "source_version": market_data.source_version,
    }

    if market_data.instrument_id != view["instrument_id"]:
        return _terminal(
            common, "OBSERVATION_ERROR",
            "INSTRUMENT_MISMATCH", OBSERVED_REASON_CODES,
            view, horizon, observed_at)

    if session is None:
        # Calendar ends before the horizon: NOT_DUE while the clock is before
        # the last known session's availability; otherwise calendar is
        # insufficient for an observation (no shift / no substitution).
        last_date = sorted({_to_date(value)
                            for value in session_dates})[-1]
        if clock < _parse_utc(hpolicy.availability_timestamp(last_date)):
            return {
                "status": "NOT_DUE",
                "decision_id": view["decision_id"],
                "horizon": horizon,
                "reason": (
                    "horizon session beyond known calendar; "
                    "observation not due"
                ),
            }
        return _terminal(
            common, "DATA_UNAVAILABLE",
            "CALENDAR_INSUFFICIENT", OBSERVED_REASON_CODES,
            view, horizon, observed_at)

    if not horizon_eligible(clock_ts, session, horizon_policy=hpolicy):
        return {
            "status": "NOT_DUE",
            "decision_id": view["decision_id"],
            "horizon": horizon,
            "reason": (
                f"clock {clock_ts} before eligibility "
                f"{hpolicy.availability_timestamp(session)}"
            ),
        }

    visible = market_data.visible(clock_ts)
    bars_by_date = {bar["date"]: bar for bar in visible}
    horizon_bar = bars_by_date.get(session.isoformat())
    if horizon_bar is None:
        return _terminal(
            common, "DATA_UNAVAILABLE",
            "NO_BAR_FOR_HORIZON_SESSION", OBSERVED_REASON_CODES,
            view, horizon, observed_at)

    as_of_text = view["as_of_date"]
    t0_bar = bars_by_date.get(as_of_text)
    decision_reference = view.get("reference_price")
    if decision_reference is not None and t0_bar is not None:
        if abs(float(decision_reference) - float(t0_bar["close"])) > 1e-6:
            return _terminal(
                common, "OBSERVATION_ERROR",
                "PRICE_BASIS_MISMATCH", OBSERVED_REASON_CODES,
                view, horizon, observed_at)
    if decision_reference is not None:
        reference_price = float(decision_reference)
        reference_source = "DECISION"
    elif t0_bar is not None:
        reference_price = float(t0_bar["close"])
        reference_source = "MARKET_T0"
    else:
        return _terminal(
            common, "DATA_UNAVAILABLE",
            "REFERENCE_PRICE_UNAVAILABLE", OBSERVED_REASON_CODES,
            view, horizon, observed_at)

    window = [
        bar for bar in visible
        if as_of_text < bar["date"] <= session.isoformat()
    ]
    raw = _raw_metrics(
        reference_price, window, float(horizon_bar["close"]))
    directional = directional_metrics(
        direction,
        raw["raw_return"],
        raw["raw_max_excursion"],
        raw["raw_min_excursion"],
    )

    record = dict(common)
    record.update({
        "outcome_status": "OBSERVED",
        "reference_price": _round(reference_price),
        "reference_price_source": reference_source,
        "horizon_price": raw["horizon_price"],
        "path_high": raw["path_high"],
        "path_low": raw["path_low"],
        "raw_return": raw["raw_return"],
        "raw_max_excursion": raw["raw_max_excursion"],
        "raw_min_excursion": raw["raw_min_excursion"],
        "future_return": directional["future_return"],
        "directional_mfe": directional["directional_mfe"],
        "directional_mae": directional["directional_mae"],
        "supersedes": None,
        "reason": None,
        "reason_code": None,
        "contract": _build_contract(
            view, horizon, "OBSERVED", observed_at,
            directional["future_return"],
            directional["directional_mae"],
            directional["directional_mfe"],
        ),
    })
    record["evidence_hash"] = observation_evidence_hash(record)
    return record


def _terminal(
    common: Mapping[str, Any],
    status: str,
    reason_code: str,
    reason_codes: Mapping[str, str],
    view: Mapping[str, Any],
    horizon: int,
    observed_at: str,
) -> dict[str, Any]:
    record = dict(common)
    record.update({
        "outcome_status": status,
        "reference_price": None,
        "reference_price_source": "NONE",
        "horizon_price": None,
        "path_high": None,
        "path_low": None,
        "raw_return": None,
        "raw_max_excursion": None,
        "raw_min_excursion": None,
        "future_return": None,
        "directional_mfe": None,
        "directional_mae": None,
        "supersedes": None,
        "reason": reason_codes.get(reason_code, reason_code),
        "reason_code": reason_code,
        "contract": _build_contract(
            view, horizon, status, observed_at, None, None, None),
    })
    record["evidence_hash"] = observation_evidence_hash(record)
    return record


# ---------------------------------------------------------------------------
# Observer orchestration + replay
# ---------------------------------------------------------------------------

class OutcomeObserver:
    """Observes all frozen horizons for one Decision; writes sidecar evidence."""

    def __init__(
        self,
        *,
        store: Any = None,
        interpretation_policy: OutcomeInterpretationPolicy | None = None,
        horizon_policy: HorizonPolicy | None = None,
    ):
        self._store = store
        self._ipolicy = interpretation_policy or OutcomeInterpretationPolicy()
        self._hpolicy = horizon_policy or HorizonPolicy()

    @property
    def store(self) -> Any:
        return self._store

    def observe(
        self,
        decision_view: Mapping[str, Any],
        *,
        session_dates: Sequence[Any],
        clock_ts: str,
        market_data: MarketDataSnapshot,
        observation_timestamp: str | None = None,
        supersedes: Mapping[int, str] | None = None,
    ) -> dict[str, Any]:
        view = validate_decision_view(decision_view)
        results = []
        written = []
        supersedes = dict(supersedes or {})
        for horizon in self._hpolicy.horizons:
            record = evaluate_horizon(
                view,
                horizon,
                session_dates=session_dates,
                clock_ts=clock_ts,
                market_data=market_data,
                interpretation_policy=self._ipolicy,
                horizon_policy=self._hpolicy,
                observation_timestamp=observation_timestamp,
            )
            if record.get("status") == "NOT_DUE":
                results.append({
                    "horizon": horizon,
                    "status": "NOT_DUE",
                    "reason": record.get("reason"),
                })
                continue
            supersede_id = supersedes.get(horizon)
            if supersede_id:
                record["supersedes"] = supersede_id
            if self._store is not None:
                meta = self._store.write(record)
                written.append({
                    "horizon": horizon,
                    "observation_id": meta["observation_id"],
                    "status": meta["status"],
                })
            results.append({
                "horizon": horizon,
                "status": record["outcome_status"],
                "observation_id": record["observation_id"],
            })
        return {
            "decision_id": view["decision_id"],
            "instrument_id": view["instrument_id"],
            "clock_ts": clock_ts,
            "horizons": [int(h) for h in self._hpolicy.horizons],
            "results": results,
            "written": written,
        }


def _semantic_fingerprint(record: Mapping[str, Any]) -> tuple[Any, ...]:
    keys = sorted(
        set(record)
        - {"evidence_hash", "observation_timestamp", "supersedes"})
    return tuple((key, record.get(key)) for key in keys)


def replay_observation(
    decision_view: Mapping[str, Any],
    *,
    horizon: int,
    session_dates: Sequence[Any],
    clock_ts: str,
    market_data: MarketDataSnapshot,
    stored_record: Mapping[str, Any],
    interpretation_policy: OutcomeInterpretationPolicy | None = None,
    horizon_policy: HorizonPolicy | None = None,
    observation_timestamp: str | None = None,
) -> dict[str, Any]:
    """Recompute an outcome; semantic payload + hash must match exactly."""
    recomputed = evaluate_horizon(
        decision_view,
        horizon,
        session_dates=session_dates,
        clock_ts=clock_ts,
        market_data=market_data,
        interpretation_policy=interpretation_policy,
        horizon_policy=horizon_policy,
        observation_timestamp=observation_timestamp,
    )
    if recomputed.get("status") == "NOT_DUE":
        raise OutcomeReplayMismatch(
            f"replay not due for horizon {horizon} at clock {clock_ts}"
        )
    if recomputed.get("evidence_hash") != stored_record.get("evidence_hash"):
        raise OutcomeReplayMismatch(
            "outcome replay evidence hash mismatch: "
            f"recomputed={recomputed.get('evidence_hash')} "
            f"recorded={stored_record.get('evidence_hash')}"
        )
    if _semantic_fingerprint(recomputed) != _semantic_fingerprint(
            stored_record):
        raise OutcomeReplayMismatch(
            "outcome replay semantic payload mismatch"
        )
    return {
        "replay_status": "MATCH",
        "horizon": horizon,
        "observation_id": stored_record["observation_id"],
        "evidence_hash": stored_record["evidence_hash"],
    }
