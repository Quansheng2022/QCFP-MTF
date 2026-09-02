# coding: utf-8
"""Daily Evidence Completeness Gate（P0-2）

每天同时验证七类闭合，状态只允许：
    DAILY_EVIDENCE_READY / DAILY_EVIDENCE_INCOMPLETE /
    DAILY_NOT_APPLICABLE / DAILY_EVIDENCE_INVALID

不再仅依赖 Runner exit code=0：
    Replay 缺失 / Outcome 缺失 / 未持久化 → INCOMPLETE
    Freeze identity break / Evidence hash 不匹配 / Replay gap /
    Critical mismatch / Duplicate decision / 篡改 → INVALID

只有全部 DoD 成立才允许 qualified_days + 1。
"""

import hashlib
import json

from .runtime_evidence import READY_VERDICTS


DAILY_STATES = ("DAILY_EVIDENCE_READY", "DAILY_EVIDENCE_INCOMPLETE",
                "DAILY_NOT_APPLICABLE", "DAILY_EVIDENCE_INVALID")


def verify_evidence_hash(artifact) -> bool:
    """按 builder 同口径重算 evidence_hash：sha256({evidence,
    ledger_bindings})。"""
    if not isinstance(artifact, dict) or not artifact.get("evidence_hash"):
        return False
    try:
        raw = json.dumps({"evidence": artifact.get("evidence"),
                          "ledger_bindings":
                              artifact.get("ledger_bindings")},
                         sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16] \
            == artifact["evidence_hash"]
    except Exception:
        return False


def evaluate_daily_evidence_gate(evidence_artifact, *, replay=None,
                                 shadow=None, outcome=None,
                                 outcome_backfill=None, persisted=None,
                                 freeze_contract=None,
                                 day_identity=None,
                                 status="") -> dict:
    """返回每日 Gate 结果 + qualified 布尔。"""
    if str(status or "").upper() == "NOT_APPLICABLE":
        return {"state": "DAILY_NOT_APPLICABLE",
                "qualified": False, "checks": {},
                "reason": "休市/维护/计划停机（不计入不中断）"}
    checks = {}
    invalid_reasons = []
    incomplete_reasons = []
    verdict = str((evidence_artifact or {}).get("verdict") or "").upper()
    # 1) Universe / Decision Ledger Closure
    decision = (evidence_artifact or {}).get("evidence", {}).get(
        "decision") or {}
    coverage = float(decision.get("coverage") or 0.0)
    checks["universe_closure"] = coverage >= 1.0 - 1e-9 \
        and int(decision.get("expected_decisions") or 0) > 0
    if not checks["universe_closure"]:
        incomplete_reasons.append("UNIVERSE_COVERAGE<100%")
    # 2) Decision Ledger Closure（duplicate=0）
    stability = (evidence_artifact or {}).get("evidence", {}).get(
        "stability") or {}
    duplicates = int(stability.get("duplicate_decisions") or 0)
    checks["decision_ledger_closure"] = duplicates == 0
    if duplicates > 0:
        invalid_reasons.append("DUPLICATE_DECISION")
    # 3) Replay Closure
    replay_section = replay or (evidence_artifact or {}).get(
        "evidence", {}).get("replay") or {}
    eligible = int(replay_section.get("replay_eligible")
                   or replay_section.get("n_eligible") or 0)
    exact = int(replay_section.get("replay_exact")
                or replay_section.get("n_exact") or 0)
    critical = int(replay_section.get("critical_replay_mismatch")
                   or replay_section.get("critical_mismatch") or 0)
    checks["replay_closure"] = eligible > 0 and eligible == exact \
        and critical == 0
    if eligible == 0:
        incomplete_reasons.append("REPLAY_MISSING")
    elif eligible != exact:
        invalid_reasons.append("REPLAY_NOT_EXACT")
    if critical > 0:
        invalid_reasons.append("CRITICAL_REPLAY_MISMATCH")
    if int(decision.get("expected_decisions") or 0) > 0 and eligible == 0:
        invalid_reasons.append("REPLAY_GAP")
    # 4) Outcome Backfill Status（errors=0 即可，成熟度单独算）
    ob = outcome_backfill or {}
    checks["outcome_backfill"] = int(ob.get("errors") or 0) == 0
    if not checks["outcome_backfill"]:
        incomplete_reasons.append("OUTCOME_BACKFILL_ERROR")
    # 5) PIT / Data Quality Closure
    checks["pit_permission_closure"] = \
        int(decision.get("pit_violations") or 0) == 0 \
        and int(decision.get("permission_violations") or 0) == 0
    if not checks["pit_permission_closure"]:
        invalid_reasons.append("PIT_OR_PERMISSION_VIOLATION")
    # 6) Evidence Hash
    checks["evidence_hash_verified"] = verify_evidence_hash(
        evidence_artifact)
    if not checks["evidence_hash_verified"]:
        invalid_reasons.append("EVIDENCE_HASH_MISMATCH")
    # 7) Projection Persistence
    checks["projection_persisted"] = bool(persisted and persisted.get(
        "evidence_id"))
    if not checks["projection_persisted"]:
        incomplete_reasons.append("PROJECTION_NOT_PERSISTED")
    # 8) Freeze Identity Consistent
    freeze = freeze_contract or {}
    identity = day_identity or {}
    breaks = []
    if freeze and identity:
        from ..governance.evidence_freeze_contract import \
            window_identity_break
        breaks = window_identity_break(freeze, identity)
    checks["freeze_identity_consistent"] = not breaks
    if breaks:
        invalid_reasons.append(
            "EVIDENCE_WINDOW_IDENTITY_BREAK:" + ",".join(breaks))
    checks["verdict_ready"] = verdict in READY_VERDICTS
    if not checks["verdict_ready"]:
        incomplete_reasons.append(f"verdict={verdict}")
    if invalid_reasons:
        state = "DAILY_EVIDENCE_INVALID"
    elif incomplete_reasons:
        state = "DAILY_EVIDENCE_INCOMPLETE"
    else:
        state = "DAILY_EVIDENCE_READY"
    qualified = state == "DAILY_EVIDENCE_READY" \
        and all(checks.values())
    return {"state": state, "qualified": qualified, "checks": checks,
            "invalid_reasons": invalid_reasons,
            "incomplete_reasons": incomplete_reasons,
            "evidence_freeze_id":
                (freeze or {}).get("evidence_freeze_id", "")}
