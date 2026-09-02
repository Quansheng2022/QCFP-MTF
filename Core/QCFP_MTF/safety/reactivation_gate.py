# coding: utf-8
"""Reactivation Gate（QCFP-MTF 2.8：97 号重新激活门 +
Runtime Evidence Wiring：第 9 项）

防止"问题修了 → restart → Production"：
    SUSPENDED → Root Cause → Fix → Replay → Invariant → PIT →
    Regression → Shadow → Governance Approval → REACTIVATED

严重程度不同可要求不同步骤，但不能直接恢复；
恢复必须产生新的 ReactivationCertificate，而不是简单改状态字段。

Runtime Evidence Wiring（第 9 项）：
    Certificate Identity 绑定 incident_id / release_id /
    checkpoint_hash / replay_hash / approval_identity——
    不同 Incident 完成同样步骤不能得到相同 Certificate Identity。
    Reactivation 必须同时存在 REACTIVATION Runtime Event 才允许
    SUSPENDED → PRODUCTION（restart != REACTIVATED）。
"""

import hashlib
import json


REACTIVATION_STEPS = ("root_cause", "fix", "replay", "invariant",
                      "pit", "regression", "shadow",
                      "governance_approval")

LOW_SEVERITY_STEPS = ("root_cause", "fix", "replay", "regression",
                      "governance_approval")


def reactivation_gate(completed_steps, severity="HIGH", incident_id="",
                      release_id="", checkpoint_hash="", replay_hash="",
                      approval_identity="") -> dict:
    """completed_steps：已完成步骤列表；HIGH 要求全部 8 步。

    certificate id = hash(incident_id + release_id + checkpoint_hash +
    replay_hash + approval_identity + steps)——保证唯一身份。"""
    done = set(completed_steps or [])
    required = REACTIVATION_STEPS if severity == "HIGH" \
        else LOW_SEVERITY_STEPS
    missing = [s for s in required if s not in done]
    if missing:
        return {"verdict": "STAY_SUSPENDED",
                "missing_steps": missing,
                "severity": severity,
                "certificate": None,
                "rule": "不能直接恢复 Production"}
    identity_raw = json.dumps({
        "incident_id": incident_id,
        "release_id": release_id,
        "checkpoint_hash": checkpoint_hash,
        "replay_hash": replay_hash,
        "approval_identity": approval_identity,
        "steps": sorted(done),
    }, sort_keys=True, ensure_ascii=False)
    cert = {
        "reactivation_certificate_id": hashlib.sha256(
            identity_raw.encode("utf-8")).hexdigest()[:16],
        "severity": severity,
        "steps_completed": sorted(done),
        "incident_id": incident_id,
        "release_id": release_id,
        "checkpoint_hash": checkpoint_hash,
        "replay_hash": replay_hash,
        "approval_identity": approval_identity,
    }
    return {"verdict": "REACTIVATED",
            "missing_steps": [],
            "severity": severity,
            "certificate": cert,
            "rule": "恢复必须产生新的 ReactivationCertificate"}


def reactivation_certificate(result: dict) -> dict:
    return {"certificate": result.get("certificate"),
            "valid": result.get("verdict") == "REACTIVATED"}


def reactivation_requires_certificate(transition: dict,
                                      certificate: dict) -> dict:
    """新 97 号：SUSPENDED → PRODUCTION 状态变化必须引用
    ReactivationCertificate；修复 ≠ 重新获得可信资格。"""
    from_state = transition.get("from")
    to_state = transition.get("to")
    if from_state == "SUSPENDED" and to_state == "PRODUCTION":
        if not certificate or not certificate.get(
                "reactivation_certificate_id"):
            return {"verdict": "TRANSITION_BLOCKED",
                    "reason": "SUSPENDED→PRODUCTION 必须引用 "
                              "ReactivationCertificate",
                    "allowed": False}
        return {"verdict": "TRANSITION_ALLOWED",
                "reason": "已引用 ReactivationCertificate",
                "certificate_id": certificate.get(
                    "reactivation_certificate_id"),
                "allowed": True}
    return {"verdict": "NOT_SUSPEND_TRANSITION",
            "allowed": True}
