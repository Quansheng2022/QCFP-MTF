# coding: utf-8
"""CANDIDATE BYTES (not importable while named .py.txt) — Governed Universe
Provider candidate (R1.2 final).

Future materialization target (AFTER Human approval, exact bytes):
    Core/QCFP_MTF/decision/publication_universe.py

Selection policy (frozen):
    decision_date = D
    For each stock: latest eligible qcfp_weekly_tactical row with
    week_end <= D, joined with hk_stock_info.is_active = 1.
    If the same stock has more than one row at its selected week_end
    -> SOURCE_DUPLICATE (fail closed; never DISTINCT-silenced).

Replay stability:
    universe identity NEVER includes run_id. run_id belongs only to
    Publication Run Provenance.

Universe source is PRE-FUSION (weekly engine output -> mtf_fusion ->
qcfp_mtf_decision); Expected Universe is NOT derived from qcfp_mtf_decision.
"""

from __future__ import annotations

import hashlib
import json

from QCFP_MTF.phase5.publication_universe import (
    PublicationUniverseSnapshot,
)


PROVIDER_ID = "QCFP-GOVERNED-UNIVERSE"
PROVIDER_VERSION = "WEEKLY-TACTICAL-2"
SOURCE = "QCFP_WEEKLY_TACTICAL"


def _selected_source_rows(conn, decision_date):
    """Raw canonical source rows [stock_code, selected_week_end, is_active]."""
    rows = conn.execute(
        "SELECT w.stock_code, MAX(w.week_end) AS selected_week_end, "
        "       h.is_active AS is_active "
        "FROM qcfp_weekly_tactical w "
        "JOIN hk_stock_info h ON h.stock_code=w.stock_code "
        "WHERE w.week_end<=? AND h.is_active=1 "
        "GROUP BY w.stock_code",
        (decision_date,)).fetchall()
    return sorted(
        {"stock_code": str(r["stock_code"]),
         "selected_week_end": str(r["selected_week_end"]),
         "is_active": int(r["is_active"])}
        for r in rows)


def _source_snapshot_hash(rows) -> str:
    raw = json.dumps(rows, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def resolve_governed_universe(
    *,
    conn,
    decision_date: str,
    run_context: dict,
) -> PublicationUniverseSnapshot:
    """READ-ONLY resolver with duplicate fail-closed and no run_id binding."""
    rows = conn.execute(
        "SELECT stock_code, week_end FROM qcfp_weekly_tactical "
        "WHERE week_end<=? AND stock_code IN ("
        "SELECT stock_code FROM hk_stock_info WHERE is_active=1)",
        (decision_date,)).fetchall()
    by_stock = {}
    for row in rows:
        code = str(row["stock_code"])
        week = str(row["week_end"])
        by_stock.setdefault(code, []).append(week)
    selected = {}
    for code, weeks in by_stock.items():
        selected_week = max(weeks)
        if weeks.count(selected_week) > 1:
            raise RuntimeError(
                f"SOURCE_DUPLICATE: {code} at {selected_week}")
        selected[code] = selected_week
    snapshot_rows = sorted(
        ({"stock_code": code,
          "selected_week_end": selected[code],
          "is_active": 1}
         for code in selected),
        key=lambda row: row["stock_code"])
    source_snapshot_hash = _source_snapshot_hash(snapshot_rows)
    symbols = sorted(selected)
    cutoff = max(selected.values()) if selected else ""
    source_identity = (
        f"{PROVIDER_ID}:{PROVIDER_VERSION}:{cutoff}:"
        f"{source_snapshot_hash}")
    return PublicationUniverseSnapshot.from_parts(
        decision_date=decision_date,
        symbols=symbols,
        source=SOURCE,
        source_identity=source_identity,
    )
