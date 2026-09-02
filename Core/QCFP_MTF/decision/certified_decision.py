# coding: utf-8
"""CertifiedDecision（QCFP-MTF 2.8：新 6 号唯一认证决策出口）

把 Continuous Validation / Incident / Production Acceptance 接到
决策出口，成为不可绕过的执行资格门：

    DecisionSnapshot
        ↓ Safety Status
        ↓ Production Acceptance
        ↓ Certification
        ↓ CertifiedDecision
        ↓ Execution

Convergence Release（新 1 号）：certify_decision 绝对 fail-closed——
废弃 boolean 默认参数，改为证据对象型：
    missing → REFUSED / UNKNOWN → REFUSED / FAIL → REFUSED /
    expired → REFUSED / scope mismatch → REFUSED / hash mismatch → REFUSED
Evidence Pack 在 Certification 内部校验，不依赖调用方额外检查。

最终不变量：CertifiedDecision 不可能在 UNKNOWN 条件下产生。
"""

import hashlib
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class CertifiedDecision:
    decision_id: str
    certificate_id: str
    snapshot: dict
    safety_status: str
    acceptance_verdict: str
    evidence_ref: dict
    release_id: str = ""
    release_manifest_hash: str = ""
    evidence_pack_id: str = ""
    evidence_pack_hash: str = ""

    def as_dict(self) -> dict:
        return {
            "decision_id": self.decision_id,
            "certificate_id": self.certificate_id,
            "snapshot": self.snapshot,
            "safety_status": self.safety_status,
            "acceptance_verdict": self.acceptance_verdict,
            "evidence_ref": self.evidence_ref,
            "release_id": self.release_id,
            "release_manifest_hash": self.release_manifest_hash,
            "evidence_pack_id": self.evidence_pack_id,
            "evidence_pack_hash": self.evidence_pack_hash,
        }


def _evidence_status(evidence) -> tuple:
    """证据对象：{"status": PASS/FAIL/UNKNOWN/MISSING/EXPIRED, ...}。
    只有 status == PASS 才通过；缺失/未知/过期/失败一律 REFUSED。"""
    if not evidence:
        return False, "MISSING"
    status = str(evidence.get("status") or "").upper()
    if status == "PASS":
        return True, ""
    return False, status or "UNKNOWN"


def certify_decision(snapshot, pit_certificate=None,
                     ledger_verification=None, replay_certificate=None,
                     governance_proof=None, production_acceptance=None,
                     safety_status=None, release_manifest=None,
                     evidence_pack=None) -> dict:
    """唯一认证出口（绝对 fail-closed）：
    任何证据 missing/UNKNOWN/FAIL/expired/scope mismatch/hash mismatch
    → REFUSED，不生成 CertifiedDecision。"""
    failures = []
    for name, evidence in (
            ("pit_certificate", pit_certificate),
            ("ledger_verification", ledger_verification),
            ("replay_certificate", replay_certificate),
            ("governance_proof", governance_proof),
            ("production_acceptance", production_acceptance)):
        ok, reason = _evidence_status(evidence)
        if not ok:
            failures.append(f"{name}:{reason}")
    # release_manifest 是身份对象而非 status 对象
    if not release_manifest or not release_manifest.get("release_id") \
            or not release_manifest.get("manifest_hash"):
        failures.append("release_manifest:UNKNOWN_OR_INCOMPLETE")
    if safety_status != "NORMAL":
        failures.append(f"safety_status:{safety_status or 'MISSING'}")
    # Evidence Pack 在 Certification 内部校验
    if not evidence_pack or not evidence_pack.get("evidence_hash") \
            or evidence_pack.get("certification") != "CERTIFIED":
        failures.append("evidence_pack:NOT_CERTIFIED_OR_MISSING")
    if failures:
        return {"certified": False, "refused": True,
                "failures": failures, "certificate": None,
                "rule": "CertifiedDecision 不可能在 UNKNOWN 条件下产生；"
                        "missing/UNKNOWN/FAIL/expired/scope/hash mismatch "
                        "一律 REFUSED"}
    snap_dict = snapshot.as_dict() if hasattr(snapshot, "as_dict") \
        else dict(snapshot)
    # PWC-1（第 4 项）：Cross-Binding——
    # A Release 的 Snapshot + B Release 的 EvidencePack + C Release 的
    # Manifest 不能因为三者单独"合法"而被组合认证。
    snap_release = snap_dict.get("release_id") or \
        getattr(snapshot, "release_id", "") or ""
    snap_manifest_hash = snap_dict.get("release_manifest_hash") or \
        getattr(snapshot, "release_manifest_hash", "") or ""
    manifest_release = (release_manifest or {}).get("release_id") or ""
    manifest_hash = (release_manifest or {}).get("manifest_hash") or ""
    pack_release = (evidence_pack or {}).get("release_id") or ""
    pack_hash = (evidence_pack or {}).get("evidence_hash") or ""
    cross_failures = []
    if snap_release and manifest_release \
            and snap_release != manifest_release:
        cross_failures.append("RELEASE_ID_MISMATCH")
    if pack_release and manifest_release \
            and pack_release != manifest_release:
        cross_failures.append("EVIDENCE_PACK_RELEASE_MISMATCH")
    if snap_manifest_hash and manifest_hash \
            and snap_manifest_hash != manifest_hash:
        cross_failures.append("MANIFEST_HASH_MISMATCH")
    if snap_dict.get("evidence_pack_hash") and pack_hash \
            and snap_dict["evidence_pack_hash"] != pack_hash:
        cross_failures.append("EVIDENCE_HASH_MISMATCH")
    if snap_dict.get("data_snapshot_id") \
            and (evidence_pack or {}).get("data_snapshot_id") \
            and snap_dict["data_snapshot_id"] != \
            (evidence_pack or {}).get("data_snapshot_id"):
        cross_failures.append("DATA_SNAPSHOT_MISMATCH")
    if snap_dict.get("universe_snapshot_id") \
            and (evidence_pack or {}).get("universe_snapshot_id") \
            and snap_dict["universe_snapshot_id"] != \
            (evidence_pack or {}).get("universe_snapshot_id"):
        cross_failures.append("UNIVERSE_SNAPSHOT_MISMATCH")
    if cross_failures:
        return {"certified": False, "refused": True,
                "failures": cross_failures, "certificate": None,
                "rule": "Cross-Binding：Snapshot/Manifest/EvidencePack "
                        "必须同属一个 Release"}
    evidence_ref = {
        "pit": "PASS", "ledger": "PASS", "replay": "PASS",
        "governance": "PASS",
        "acceptance": (production_acceptance or {}).get("status", "PASS"),
        "safety": safety_status,
    }
    release_id = (release_manifest or {}).get("release_id") or ""
    release_manifest_hash = (release_manifest or {}).get("manifest_hash") or ""
    evidence_pack_hash = (evidence_pack or {}).get("evidence_hash") or ""
    raw = json.dumps({"decision_id": snap_dict.get("decision_id"),
                      "snapshot": snap_dict,
                      "evidence_ref": evidence_ref,
                      "release_id": release_id,
                      "evidence_pack_hash": evidence_pack_hash},
                     sort_keys=True, ensure_ascii=False, default=str)
    certificate_id = hashlib.sha256(
        raw.encode("utf-8")).hexdigest()[:16]
    cd = CertifiedDecision(
        decision_id=snap_dict.get("decision_id") or "",
        certificate_id=certificate_id,
        snapshot=snap_dict,
        safety_status=safety_status,
        acceptance_verdict=(production_acceptance or {}).get(
            "status", "ACCEPTED"),
        evidence_ref=evidence_ref,
        release_id=release_id,
        release_manifest_hash=release_manifest_hash,
        evidence_pack_id=evidence_pack_hash,
        evidence_pack_hash=evidence_pack_hash)
    return {"certified": True, "refused": False,
            "failures": [], "certificate": cd}


def assert_evidence_pack_bound(certified_decision) -> dict:
    """新 14 号：CertifiedDecision.release_id → EvidencePackID →
    EvidencePackHash 必须进入 Ledger；缺 Evidence Pack → NOT CERTIFIED。"""
    cd = certified_decision
    bound = bool(cd.release_id and cd.evidence_pack_id
                 and cd.evidence_pack_hash)
    return {
        "release_id": cd.release_id,
        "evidence_pack_id": cd.evidence_pack_id,
        "evidence_pack_hash": cd.evidence_pack_hash,
        "bound": bound,
        "certification": "CERTIFIED" if bound else "NOT_CERTIFIED",
        "rule": "decision → release → evidence pack；"
                "缺 Evidence Pack 直接 NOT CERTIFIED",
    }


def record_certificate(conn, certified_decision,
                       created_at="") -> int:
    """持久化 CertifiedDecision 到 qcfp_decision_certificate
    （Runtime Evidence Wiring：第 2 项 identity cross-bind）。

    Runtime Event 写入前通过该表验证 certificate.decision_id /
    certificate.release_id 与 event 一致；缺表 → 显式抛错，不静默跳过。"""
    import json as _json
    import hashlib as _hashlib
    snap = certified_decision.snapshot if hasattr(
        certified_decision, "snapshot") else {}
    snapshot_hash = _hashlib.sha256(
        _json.dumps(snap, sort_keys=True, ensure_ascii=False,
                    default=str).encode("utf-8")).hexdigest()[:16]
    cur = conn.execute(
        "INSERT OR IGNORE INTO qcfp_decision_certificate "
        "(certificate_id, decision_id, release_id, snapshot_hash, "
        "evidence_pack_hash, created_at) VALUES (?,?,?,?,?,?)",
        (certified_decision.certificate_id,
         certified_decision.decision_id,
         certified_decision.release_id,
         snapshot_hash,
         certified_decision.evidence_pack_hash or "",
         created_at))
    return cur.rowcount
