# coding: utf-8
"""P5-E / WP5.2 — governed Canonical-vs-Shadow divergence layer.

Wraps the frozen baseline semantics (governance/shadow_divergence.py reason
codes) into a deterministic D0-D9/DX taxonomy with severity, explanation,
replay verification and review lifecycle. Consumes P5-B DivergenceContract.

Hard rules:
    * divergence is data/evidence, never Authority
    * no Canonical write-back / no production action / no promotion authority
    * DX = CRITICAL; replay mismatch = CRITICAL; CRITICAL cannot auto-close
    * deterministic severity only; no aggregate score
"""

from __future__ import annotations

from typing import Any, Mapping

from .contracts import DIVERGENCE_SEVERITIES, DivergenceContract, contract_dict


class DivergenceError(RuntimeError):
    """Fail-closed divergence framework error."""


DIVERGENCE_CODES = (
    "D0", "D1", "D2", "D3", "D4", "D5",
    "D6", "D7", "D8", "D9", "DX",
)

REASON_CODE_MAP = {
    "D0": "NO_DIVERGENCE",
    "D1": "DATA_DELTA",
    "D2": "CONFIG_DELTA",
    "D3": "VERSION_DELTA",
    "D4": "GOVERNANCE_INTERCEPTION",
    "D5": "FSM_STATE_DELTA",
    "D6": "TARGET_DELTA",
    "D7": "EXECUTION_CONSTRAINT",
    "D8": "DECISION_PATH_DELTA",
    "D9": "MODEL_DELTA",
    "DX": "UNEXPLAINED_DIVERGENCE",
}

REVIEW_STATES = (
    "DETECTED", "CLASSIFIED", "EXPLAINED", "REPLAYED",
    "REVIEWED", "CLOSED", "ESCALATED",
)

REVIEW_TRANSITIONS = {
    "DETECTED": ("CLASSIFIED",),
    "CLASSIFIED": ("EXPLAINED",),
    "EXPLAINED": ("REPLAYED",),
    "REPLAYED": ("REVIEWED",),
    "REVIEWED": ("CLOSED", "ESCALATED"),
    "CLOSED": (),
    "ESCALATED": (),
}

REQUIRED_COMPARISON_IDENTITY = (
    "decision_id",
    "source_snapshot_id",
    "evidence_pack_id",
    "config_hash",
    "code_identity",
)

REQUIRED_VERSION_BASIS = (
    "rule_version",
    "model_version",
)

REQUIRED_COMPARISON_FIELDS = (
    "permission",
    "fsm_state",
    "execution_cap",
    "decision_path",
    "target_position",
    "model_output",
)


def validate_comparison_evidence(
    canonical_view: Mapping[str, Any],
    shadow_view: Mapping[str, Any],
) -> None:
    """Any missing/empty required governed evidence fails closed (DX)."""
    for side, view in (("canonical", canonical_view),
                       ("shadow", shadow_view)):
        for field in REQUIRED_COMPARISON_IDENTITY + REQUIRED_VERSION_BASIS:
            value = view.get(field)
            if value is None or value == "":
                raise DivergenceError(
                    f"{side} missing required comparison evidence: {field}"
                )
        for field in REQUIRED_COMPARISON_FIELDS:
            value = view.get(field)
            if value is None or value == "" or value == []:
                raise DivergenceError(
                    f"{side} missing required comparison field: {field}"
                )


def reason_code_for(code: str) -> str:
    if code not in REASON_CODE_MAP:
        raise DivergenceError(f"unknown divergence code: {code!r}")
    return f"{code}_{REASON_CODE_MAP[code]}"


def normalize_decision(record: Mapping[str, Any]) -> dict[str, Any]:
    """Immutable normalization into a canonical comparison view."""
    if not isinstance(record, Mapping) or not record:
        raise DivergenceError("comparison record missing/invalid -> DX")
    src = dict(record)
    out: dict[str, Any] = {}
    key_map = {
        "decision_id": ("decision_id", "decision_id"),
        "source_snapshot_id": ("source_snapshot_id", "source_snapshot_id"),
        "evidence_pack_id": ("evidence_pack_id", "evidence_pack_id"),
        "config_hash": ("config_hash", "config_hash"),
        "code_identity": ("code_identity", "code_identity"),
        "rule_version": ("rule_version", "rule_version"),
        "model_version": ("model_version", "model_version"),
        "permission": (
            "institutional_permission", "permission"),
        "fsm_state": ("next_fsm_state", "fsm_state"),
        "target_position": ("target_position", "target_position"),
        "execution_cap": ("execution_cap", "execution_cap"),
        "decision_path": ("decision_path", "decision_path"),
        "model_output": ("model_output", "model_output"),
    }
    for key, (canonical_key, shadow_key) in key_map.items():
        value = src.get(canonical_key, src.get(shadow_key))
        out[key] = list(value) if isinstance(value, (list, tuple)) \
            else value
    return out


def _identity_consistent(c: Mapping[str, Any], s: Mapping[str, Any]) -> bool:
    cid, sid = c.get("decision_id"), s.get("decision_id")
    if not cid or not sid:
        return False
    if cid != sid:
        return False
    return True


def classify_divergence(
    canonical: Mapping[str, Any],
    shadow: Mapping[str, Any],
) -> dict[str, Any]:
    """Deterministic precedence classification (see module docstring)."""
    try:
        c = normalize_decision(canonical)
        s = normalize_decision(shadow)
        validate_comparison_evidence(c, s)
    except DivergenceError:
        return {
            "diverged": True,
            "code": "DX",
            "reason_code": reason_code_for("DX"),
            "changed_fields": ["identity_or_record"],
            "explanation": "comparison evidence invalid/missing -> DX",
            "severity": "CRITICAL",
            "severity_rationale": "DX / missing comparison evidence",
        }

    def differs(key: str) -> bool:
        cv, sv = c.get(key), s.get(key)
        if isinstance(cv, list) and isinstance(sv, list):
            return cv != sv
        return cv != sv

    changed = [key for key in (
        "decision_id", "source_snapshot_id", "evidence_pack_id",
        "config_hash", "code_identity", "rule_version", "model_version",
        "permission", "fsm_state", "execution_cap", "decision_path",
        "target_position", "model_output",
    ) if differs(key)]

    if not changed:
        return {
            "diverged": False,
            "code": "D0",
            "reason_code": reason_code_for("D0"),
            "changed_fields": [],
            "explanation": "canonical and shadow decisions match (D0)",
            "severity": "INFO",
            "severity_rationale": "exact match -> INFO",
        }

    if not _identity_consistent(c, s):
        return {
            "diverged": True,
            "code": "DX",
            "reason_code": reason_code_for("DX"),
            "changed_fields": changed,
            "explanation": "identity contradiction with incompatible "
                           "provenance -> DX",
            "severity": "CRITICAL",
            "severity_rationale": "identity contradiction -> CRITICAL",
        }

    precedence = (
        ("source_snapshot_id", "D1"),
        ("evidence_pack_id", "D1"),
        ("config_hash", "D2"),
        ("code_identity", "D3"),
        ("rule_version", "D3"),
        ("model_version", "D3"),
        ("permission", "D4"),
        ("fsm_state", "D5"),
        ("execution_cap", "D7"),
        ("decision_path", "D8"),
        ("target_position", "D6"),
    )
    for key, code in precedence:
        if differs(key):
            return {
                "diverged": True,
                "code": code,
                "reason_code": reason_code_for(code),
                "changed_fields": changed,
                "explanation": (
                    f"{code}: {key} differs "
                    f"canonical={c.get(key)!r} shadow={s.get(key)!r}; "
                    f"changed_fields={changed}"
                ),
                "severity": _severity_for(code),
                "severity_rationale": _severity_rationale(code),
            }

    if "model_output" not in changed:
        return {
            "diverged": True,
            "code": "DX",
            "reason_code": reason_code_for("DX"),
            "changed_fields": changed,
            "explanation": (
                "residual difference lacks an explainable causal basis "
                f"and model_output is not the delta -> DX; "
                f"changed_fields={changed}"
            ),
            "severity": "CRITICAL",
            "severity_rationale": "unexplained residual without causal "
                                  "basis -> CRITICAL",
        }
    # D9 = full-evidence residual model delta (never a dumping ground).
    return {
        "diverged": True,
        "code": "D9",
        "reason_code": reason_code_for("D9"),
        "changed_fields": changed,
        "explanation": (
            "D9: identical governed identity/version/config yet model "
            f"output differs; changed_fields={changed}"
        ),
        "severity": "HIGH",
        "severity_rationale": "unexplained model delta with complete "
                              "evidence -> HIGH",
    }


def _severity_for(code: str) -> str:
    table = {
        "D0": "INFO",
        "D4": "LOW",
        "D1": "MEDIUM",
        "D2": "MEDIUM",
        "D3": "MEDIUM",
        "D7": "MEDIUM",
        "D5": "HIGH",
        "D6": "HIGH",
        "D8": "HIGH",
        "D9": "HIGH",
        "DX": "CRITICAL",
    }
    return table[code]


def _severity_rationale(code: str) -> str:
    if code == "DX":
        return "DX / unexplained -> CRITICAL"
    if code == "D0":
        return "exact match -> INFO"
    if code == "D4":
        return "expected safe governance interception -> LOW"
    if code in ("D1", "D2", "D3", "D7"):
        return "explained data/config/version/execution delta -> MEDIUM"
    return "FSM/path/target/model delta -> HIGH"


def divergence_severity(result: Mapping[str, Any]) -> dict[str, str]:
    code = result["code"]
    return {
        "severity": _severity_for(code),
        "rationale": _severity_rationale(code),
    }


def validate_divergence_record(record: Mapping[str, Any]) -> None:
    """Fail closed on semantically inconsistent taxonomy records."""
    code = record.get("code")
    reason_code = record.get("reason_code")
    severity = record.get("severity")
    review_state = record.get("review_state")
    if code not in DIVERGENCE_CODES:
        raise DivergenceError(f"invalid divergence code: {code!r}")
    if reason_code != reason_code_for(code):
        raise DivergenceError(
            f"reason_code mismatch: code={code} "
            f"expected={reason_code_for(code)} got={reason_code!r}"
        )
    expected_severity = _severity_for(code)
    if severity != expected_severity:
        raise DivergenceError(
            f"severity mismatch: code={code} "
            f"expected={expected_severity} got={severity!r}"
        )
    if review_state not in REVIEW_STATES:
        raise DivergenceError(
            f"invalid review_state: {review_state!r}"
        )


def build_divergence_contract(
    canonical: Mapping[str, Any],
    shadow: Mapping[str, Any],
    *,
    review_state: str = "DETECTED",
) -> dict[str, Any]:
    if review_state not in REVIEW_STATES:
        raise DivergenceError(f"invalid review_state: {review_state!r}")
    result = classify_divergence(canonical, shadow)
    canonical_decision_id = str(canonical.get("decision_id") or "")
    shadow_decision_id = str(shadow.get("decision_id") or "")
    canonical_ref = str(canonical.get("source_snapshot_id") or "")
    shadow_ref = str(shadow.get("shadow_run_id") or "")
    for value, label in (
        (canonical_decision_id, "canonical_decision_id"),
        (shadow_decision_id, "shadow_decision_id"),
        (canonical_ref, "canonical evidence ref"),
        (shadow_ref, "shadow_run_id evidence ref"),
    ):
        if not value or value == "":
            raise DivergenceError(
                f"cannot build complete DivergenceContract: {label} empty"
            )
    carrier = DivergenceContract(
        canonical_decision_id=canonical_decision_id,
        shadow_decision_id=shadow_decision_id,
        diverged=bool(result["diverged"]),
        severity=result["severity"],
        explanation=result["explanation"],
        review_state=review_state,
        reason_code=result["reason_code"],
        evidence_refs=(canonical_ref, shadow_ref),
    )
    return contract_dict(carrier)


def advance_review_state(
    divergence_record: Mapping[str, Any],
    target: str,
) -> str:
    validate_divergence_record(divergence_record)
    current = divergence_record.get("review_state")
    severity = divergence_record.get("severity")
    reason_code = divergence_record.get("reason_code")
    if current not in REVIEW_STATES or target not in REVIEW_STATES:
        raise DivergenceError("unknown review state")
    if target not in REVIEW_TRANSITIONS.get(current, ()):
        raise DivergenceError(
            f"illegal review transition {current} -> {target}"
        )
    critical_markers = ("CRITICAL", "UNEXPLAINED_DIVERGENCE",
                        "REPLAY_SHADOW_MISMATCH",
                        "REPLAY_DIVERGENCE_CLASSIFICATION_MISMATCH")
    if severity == "CRITICAL" and target == "CLOSED":
        raise DivergenceError(
            "CRITICAL divergence cannot auto-close; must ESCALATE"
        )
    if reason_code and any(
        marker in str(reason_code) for marker in critical_markers
    ) and target == "CLOSED":
        raise DivergenceError(
            f"record {reason_code} cannot auto-close; must ESCALATE"
        )
    return target


def replay_divergence(
    canonical: Mapping[str, Any],
    original_divergence: Mapping[str, Any],
    store: Any,
    shadow_run_id: str,
    evaluator: Any,
    *,
    expected: Mapping[str, str],
) -> dict[str, Any]:
    """Reuse P5-C replay_shadow_run; mismatch escalates to CRITICAL."""
    from .shadow_replay import ReplayMismatch, replay_shadow_run

    try:
        outcome = replay_shadow_run(
            store, shadow_run_id, evaluator,
            expected=expected)
    except ReplayMismatch as exc:
        return {
            "replay_status": "MISMATCH",
            "replay_run_id": None,
            "severity": "CRITICAL",
            "review_state": "ESCALATED",
            "reason_code": "REPLAY_SHADOW_MISMATCH",
            "reason": str(exc),
            "divergence_reproducible": False,
        }

    replay_run_id = outcome["replay_shadow_run_id"]
    run_identity = store.read(replay_run_id)
    decision = store.read_decision(replay_run_id)
    replayed_shadow = {
        key: run_identity.get(key)
        for key in (
            "decision_id", "source_snapshot_id", "evidence_pack_id",
            "config_hash", "code_identity", "rule_version",
            "model_version", "as_of_timestamp",
        )
    }
    replayed_shadow.update(dict(decision.get("output") or {}))
    recomputed = classify_divergence(canonical, replayed_shadow)
    original_keys = _classification_fingerprint(original_divergence)
    replay_keys = _classification_fingerprint(recomputed)
    if original_keys != replay_keys:
        return {
            "replay_status": "MISMATCH",
            "replay_run_id": replay_run_id,
            "severity": "CRITICAL",
            "review_state": "ESCALATED",
            "reason_code": "REPLAY_DIVERGENCE_CLASSIFICATION_MISMATCH",
            "reason": (
                f"original={original_keys} replay={replay_keys}"
            ),
            "divergence_reproducible": False,
            "recomputed_classification": recomputed,
        }
    return {
        "replay_status": "MATCH",
        "replay_run_id": replay_run_id,
        "severity": None,
        "review_state": "REPLAYED",
        "divergence_reproducible": True,
        "recomputed_classification": recomputed,
    }


def divergence_blocks(result: Mapping[str, Any]) -> dict[str, Any]:
    severity = result.get("severity")
    blocked = severity == "CRITICAL" or result.get("diverged") and \
        result.get("code") in ("DX",)
    return {
        "blocked": bool(blocked),
        "reason": (
            "CRITICAL / DX divergence requires escalation"
            if blocked else "no promotion blocker from this divergence record"
        ),
        "is_authority": False,
    }


def _classification_fingerprint(
    result: Mapping[str, Any],
) -> tuple[Any, ...]:
    """Deterministic replay fingerprint incl. causal changed_fields."""
    return (
        str(result.get("code")),
        str(result.get("reason_code")),
        bool(result.get("diverged")),
        str(result.get("severity")),
        tuple(sorted(str(x) for x in result.get("changed_fields", ()))),
    )
