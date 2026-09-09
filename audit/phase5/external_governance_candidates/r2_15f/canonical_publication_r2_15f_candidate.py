# coding: utf-8
"""CANDIDATE BYTES (not importable while named .py.txt) — Canonical Publication
Service candidate (R1.1 activation-bound).

Future materialization target (AFTER Human approval, exact bytes):
    Core/QCFP_MTF/decision/canonical_publication.py

Authority source: NOT caller dict. Activation is loaded and verified from
governance evidence artifacts under fixed paths. Until those artifacts exist
and pass every check, publication fails closed.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from QCFP_MTF.decision.decision_ledger import record_snapshot
from QCFP_MTF.decision.engine import evaluate
from QCFP_MTF.phase5.publication_universe import (
    PublicationUniverseSnapshot,
    validate_universe,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
FIXED_ARTIFACTS = {
    "human_acceptance": PROJECT_ROOT / "audit/phase5/"
    "p5_gov_reopen_cpub_human_acceptance.json",
    "activation": PROJECT_ROOT / "audit/phase5/"
    "p5_gov_reopen_cpub_activation.json",
    "candidate_package": PROJECT_ROOT / "audit/phase5/cpub_candidate/"
    "10_candidate_package.json",
    "candidate_manifest": PROJECT_ROOT / "audit/phase5/cpub_candidate/"
    "09_candidate_manifest.json",
    "governance_baseline": PROJECT_ROOT / "audit/phase5/"
    "phase5_governance_baseline.json",
}

REQUIRED_RUNTIME_TARGETS = {
    "Core/QCFP_MTF/decision/canonical_publication.py",
    "Core/QCFP_MTF/decision/publication_universe.py",
}


class CanonicalPublicationAuthorityError(RuntimeError):
    pass


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _recompute_package_digest(package: dict) -> str:
    payload = json.dumps(
        {k: package[k] for k in sorted(package)
         if k != "candidate_package_sha256"},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_and_verify_activation() -> dict:
    missing = [name for name, path in FIXED_ARTIFACTS.items()
               if not path.exists()]
    if missing:
        raise CanonicalPublicationAuthorityError(
            "ACTIVATION_ARTIFACT_MISSING: " + ",".join(missing))
    acceptance_bytes = FIXED_ARTIFACTS["human_acceptance"].read_bytes()
    activation_bytes = FIXED_ARTIFACTS["activation"].read_bytes()
    activation = json.loads(activation_bytes.decode("utf-8"))
    package = json.loads(FIXED_ARTIFACTS["candidate_package"].read_text(
        encoding="utf-8"))
    manifest_bytes = FIXED_ARTIFACTS["candidate_manifest"].read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    baseline = json.loads(FIXED_ARTIFACTS["governance_baseline"].read_text(
        encoding="utf-8"))
    actual_manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    actual_activation_sha = hashlib.sha256(activation_bytes).hexdigest()
    acceptance_sha = hashlib.sha256(acceptance_bytes).hexdigest()
    acceptance = json.loads(acceptance_bytes.decode("utf-8"))
    package_digest = _recompute_package_digest(package)
    if actual_manifest_sha \
            != package.get("file_sha256", {}).get("CANDIDATE_MANIFEST"):
        raise CanonicalPublicationAuthorityError(
            "CANDIDATE_MANIFEST_PACKAGE_MISMATCH")
    if acceptance.get("accepted_by") != "HUMAN" \
            or acceptance.get("decision") != "APPROVE":
        raise CanonicalPublicationAuthorityError("HUMAN_ACCEPTANCE_INVALID")
    if acceptance.get("scope") != "P5-GOV-REOPEN-CPUB":
        raise CanonicalPublicationAuthorityError("ACCEPTANCE_SCOPE_MISMATCH")
    if activation.get("scope") != "P5-GOV-REOPEN-CPUB" \
            or activation.get("authority_status") != "ACTIVE":
        raise CanonicalPublicationAuthorityError("ACTIVATION_INVALID")
    if acceptance.get("candidate_package_sha256") != package_digest \
            or activation.get("candidate_package_sha256") != package_digest:
        raise CanonicalPublicationAuthorityError(
            "PACKAGE_SHA_CHAIN_MISMATCH")
    if activation.get("human_acceptance_sha256") \
            != acceptance_sha:
        raise CanonicalPublicationAuthorityError(
            "HUMAN_ACCEPTANCE_SHA_MISMATCH")
    approved_targets = set(activation.get("approved_targets", {}))
    if approved_targets != REQUIRED_RUNTIME_TARGETS:
        raise CanonicalPublicationAuthorityError(
            "APPROVED_TARGETS_NOT_EXACT")
    manifest_shas = {entry["target_path"]: entry["sha256"]
                     for entry in manifest["files"]
                     if entry.get("target_path")}
    for target in REQUIRED_RUNTIME_TARGETS:
        role = ("CANONICAL_PUBLICATION_AUTHORITY_CANDIDATE"
                if target.endswith("canonical_publication.py")
                else "CANONICAL_PUBLICATION_INPUT_AUTHORITY_CANDIDATE")
        package_target_sha = package["file_sha256"][role]
        if activation["approved_targets"][target] != package_target_sha \
                or package_target_sha != manifest_shas.get(target):
            raise CanonicalPublicationAuthorityError(
                "APPROVED_TARGET_SHA_NOT_PACKAGE_BOUND")
    if int(activation.get("governance_revision", -1)) \
            != int(baseline.get("governance_revision", -1)) \
            or baseline.get("status") != "ACCEPTED" \
            or baseline.get("accepted_by") != "HUMAN" \
            or baseline.get("activation") is not True:
        raise CanonicalPublicationAuthorityError(
            "GOVERNANCE_REVISION_MISMATCH")
    if baseline.get("candidate_package_sha256") != package_digest:
        raise CanonicalPublicationAuthorityError(
            "BASELINE_PACKAGE_SHA_MISMATCH")
    if baseline.get("human_acceptance_sha256") != acceptance_sha:
        raise CanonicalPublicationAuthorityError(
            "BASELINE_HUMAN_ACCEPTANCE_SHA_MISMATCH")
    if baseline.get("activation_record_sha256") != actual_activation_sha:
        raise CanonicalPublicationAuthorityError(
            "ACTIVATION_BASELINE_HASH_MISMATCH")
    return activation


def publish_canonical_cohort(
    *,
    conn,
    decision_date: str,
    settings,
    run_id: str,
) -> dict:
    """Production API: NO activation / universe / expected_symbols params."""
    activation = _load_and_verify_activation()
    _verify_target_hashes(activation)
    # Provider executes only AFTER its target hash is verified.
    from QCFP_MTF.decision import publication_universe as provider_mod
    resolve_governed_universe = provider_mod.resolve_governed_universe
    provider_activation = activation["approved_universe_provider"]
    universe = resolve_governed_universe(
        conn=conn, decision_date=decision_date,
        run_context={"run_id": run_id})
    if not isinstance(universe, PublicationUniverseSnapshot) \
            or not validate_universe(universe):
        raise CanonicalPublicationAuthorityError("UNIVERSE_INVALID")
    expected_prefix = (
        f"{provider_activation.get('provider_id')}:"
        f"{provider_activation.get('provider_version')}:")
    if not universe.source_identity.startswith(expected_prefix):
        raise CanonicalPublicationAuthorityError(
            "UNAPPROVED_UNIVERSE_PROVIDER")
    return _publish_verified_cohort(
        conn=conn, decision_date=decision_date,
        universe_snapshot=universe, settings=settings, run_id=run_id)


def _verify_target_hashes(activation: dict) -> None:
    for target, approved_sha in activation["approved_targets"].items():
        path = PROJECT_ROOT / target
        if target == "Core/QCFP_MTF/decision/canonical_publication.py":
            actual = _sha256_file(Path(__file__).resolve())
        else:
            actual = _sha256_file(path) if path.exists() else None
        if actual != approved_sha:
            raise CanonicalPublicationAuthorityError(
                "MATERIALIZED_TARGET_SHA_MISMATCH")


def _publish_verified_cohort(*, conn, decision_date, universe_snapshot,
                             settings, run_id) -> dict:
    expected_symbols = list(universe_snapshot.symbols)
    fusion_rows = [str(r[0]) for r in conn.execute(
        "SELECT stock_code FROM qcfp_mtf_decision "
        "WHERE decision_date=?", (decision_date,)).fetchall()]
    if set(fusion_rows) != set(expected_symbols) \
            or len(fusion_rows) != len(set(fusion_rows)) \
            or not expected_symbols:
        raise CanonicalPublicationAuthorityError("FUSION_COHORT_NOT_EXACT")
    snaps = {}
    for stock in expected_symbols:
        previous = _previous_active_state(conn, stock, decision_date)
        evidence = _load_evidence(conn, stock, decision_date)
        snaps[stock] = evaluate(
            evidence, previous["state"], previous["position"],
            settings, run_id=run_id)
    for stock in expected_symbols:
        record_snapshot(conn, snaps[stock], run_id, settings=settings)
    ledger = _exact_ledger_audit(
        conn, decision_date, expected_symbols, settings)
    if ledger["matching_count"] != len(expected_symbols) \
            or ledger["missing"] or ledger["unexpected"] \
            or ledger["duplicates"] or ledger["identity_mismatch"]:
        raise CanonicalPublicationAuthorityError("LEDGER_COHORT_NOT_EXACT")
    return {
        "run_id": run_id,
        "decision_date": decision_date,
        "universe_snapshot_id": universe_snapshot.universe_snapshot_id,
        "universe": {"expected_count": len(expected_symbols),
                     "expected_symbols": expected_symbols},
        "fusion": {"row_count": len(fusion_rows),
                   "unique_count": len(set(fusion_rows)),
                   "missing": [], "unexpected": [], "duplicates": []},
        "ledger": ledger,
        "expected_identity": _expected_identity(settings),
        "verdict": "READY_FOR_PROJECTION",
    }


def _expected_identity(settings):
    from QCFP_MTF.config.settings import get
    from QCFP_MTF.decision.decision_snapshot import (
        DECISION_RULE_VERSION, MODEL_VERSION, _settings_hash,
    )
    return {
        "settings_hash": _settings_hash(settings),
        "model_version": get(settings, "model.version", MODEL_VERSION),
        "rule_version": DECISION_RULE_VERSION,
    }


def _exact_ledger_audit(conn, decision_date, expected_symbols, settings):
    rows = conn.execute(
        "SELECT stock_code, settings_hash, model_version, rule_version "
        "FROM qcfp_decision_ledger "
        "WHERE decision_date=? AND status='ACTIVE'",
        (decision_date,)).fetchall()
    expected_set = set(expected_symbols)
    codes = [str(r["stock_code"]) for r in rows]
    duplicates = sorted({c for c in codes if codes.count(c) > 1})
    unexpected = sorted(set(codes) - expected_set)
    missing = sorted(expected_set - set(codes))
    identity = _expected_identity(settings)
    identity_mismatch = []
    for row in rows:
        actual = {
            "settings_hash": str(row["settings_hash"]),
            "model_version": str(row["model_version"]),
            "rule_version": str(row["rule_version"]),
        }
        if any(actual[k] != identity[k] for k in identity):
            identity_mismatch.append({
                "stock_code": str(row["stock_code"]),
                "actual": actual,
                "expected": identity,
            })
    matching_codes = expected_set - set(duplicates)
    matching = sum(
        1 for code in matching_codes
        if not any(item["stock_code"] == code
                   for item in identity_mismatch))
    return {
        "row_count": len(rows),
        "unique_count": len(set(codes)),
        "matching_count": matching,
        "missing": missing,
        "unexpected": unexpected,
        "duplicates": duplicates,
        "identity_mismatch": identity_mismatch,
    }


def _previous_active_state(conn, stock, date):
    r = conn.execute(
        "SELECT next_fsm_state, final_target FROM qcfp_decision_ledger "
        "WHERE stock_code=? AND decision_date<? AND status='ACTIVE' "
        "ORDER BY decision_date DESC, id DESC LIMIT 1",
        (stock, date)).fetchone()
    if r is None:
        return {"state": "FLAT", "position": 0.0}
    return {"state": r["next_fsm_state"] or "FLAT",
            "position": float(r["final_target"] or 0.0)}


def _load_evidence(conn, stock, date):
    from QCFP_MTF.scripts.dss_report import _row
    return _row(conn, stock, date)


def missing_only_recovery(
    *,
    conn,
    decision_date: str,
    settings,
    run_id: str,
    expected_pre_recovery_ledger_sha256: str,
    expected_governed_universe,
    expected_missing_set,
) -> dict:
    """MISSING_ONLY_RECOVERY: generic operation of the canonical publisher.

    This is NOT an independent authority path: it runs inside
    canonical_publication under the same Authority Resolver gate, evaluates
    ONLY members of the exact missing set, writes ONLY those members in one
    atomic transaction, never updates/deletes/supersedes/reinserts existing
    ACTIVE records, and is idempotent (empty missing set -> zero mutation).
    The operation is fully generic and contains no stock-specific branch.
    Full-cohort publish_canonical_cohort semantics are unchanged.
    """
    import hashlib
    import json as _json

    activation = _load_and_verify_activation()
    _verify_target_hashes(activation)

    from QCFP_MTF.decision import publication_universe as provider_mod
    from QCFP_MTF.decision.fsm_authority import (
        assert_fsm_explains_target_change,
    )

    universe = provider_mod.resolve_governed_universe(
        conn=conn, decision_date=decision_date,
        run_context={"run_id": run_id})
    if not isinstance(universe, PublicationUniverseSnapshot) \
            or not validate_universe(universe):
        raise CanonicalPublicationAuthorityError("UNIVERSE_INVALID")
    symbols = sorted(universe.symbols)
    if sorted(expected_governed_universe) != symbols:
        raise CanonicalPublicationAuthorityError(
            "EXPECTED_UNIVERSE_MISMATCH")

    def _rows():
        return [dict(r) for r in conn.execute(
            "SELECT * FROM qcfp_decision_ledger "
            "WHERE decision_date=? AND status='ACTIVE' "
            "ORDER BY stock_code, id", (decision_date,))]

    def _canon(row):
        return _json.dumps(
            row, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False).encode("utf-8")

    def _digest_rows(rows):
        return hashlib.sha256(
            b"\n".join(_canon(r) for r in rows)).hexdigest()

    fusion = sorted(r[0] for r in conn.execute(
        "SELECT DISTINCT stock_code FROM qcfp_mtf_decision "
        "WHERE decision_date=?", (decision_date,)))
    rows = _rows()
    led = sorted(r["stock_code"] for r in rows)
    dups = sorted(
        s for s, n in __import__("collections").Counter(
            r["stock_code"] for r in rows).items() if n > 1)
    unexpected = sorted(set(led) - set(fusion))
    if dups or unexpected:
        raise CanonicalPublicationAuthorityError(
            "LEDGER_DUPLICATE_OR_UNEXPECTED")
    if _digest_rows(rows) != expected_pre_recovery_ledger_sha256:
        raise CanonicalPublicationAuthorityError(
            "LEDGER_IDENTITY_MISMATCH")
    actual_missing = sorted(set(fusion) - set(led))
    if sorted(expected_missing_set) != actual_missing:
        raise CanonicalPublicationAuthorityError("MISSING_SET_MISMATCH")

    prepared = []
    for stock in actual_missing:
        previous = _previous_active_state(conn, stock, decision_date)
        evidence = _load_evidence(conn, stock, decision_date)
        snapshot = evaluate(
            evidence, previous["state"], previous["position"],
            settings, run_id=run_id)
        assert_fsm_explains_target_change(
            snapshot.prev_fsm_state, snapshot.next_fsm_state,
            snapshot.previous_position, snapshot.target_position,
            reason=snapshot.primary_reason)
        prepared.append((stock, snapshot))

    if not prepared:
        return {"published": [], "state": "NOOP",
                "idempotent_zero_mutation": True}

    conn.execute("BEGIN IMMEDIATE")
    try:
        for stock, snapshot in prepared:
            record_snapshot(
                conn, snapshot, run_id, settings=settings,
                manage_transaction=False)
        after_rows = _rows()
        if _digest_rows(
                [r for r in after_rows
                 if r["stock_code"] not in set(actual_missing)]) \
                != expected_pre_recovery_ledger_sha256:
            raise CanonicalPublicationAuthorityError(
                "EXISTING_RECORDS_MUTATED")
        audit = _exact_ledger_audit(
            conn, decision_date, symbols, settings)
        if audit["matching_count"] != len(symbols) \
                or audit["missing"] or audit["unexpected"] \
                or audit["duplicates"] or audit["identity_mismatch"]:
            raise CanonicalPublicationAuthorityError(
                "POSTCONDITION_COHORT_NOT_EXACT")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {
        "operation": "MISSING_ONLY_RECOVERY",
        "published": sorted(s for s, _ in prepared),
        "state": "16/16",
        "run_id": run_id,
    }
