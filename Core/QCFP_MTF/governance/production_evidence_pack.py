# coding: utf-8
"""Production Evidence Pack（QCFP-MTF 2.8：91 号生产证据包）

把生产资格压缩成一份可审计证据包：
    ReleaseManifest / ValidationCertificate / PIT Certificate /
    OOS Result / Ablation Result / Stress Result / Replay Result /
    Shadow Result / Governance Approval / Evidence Hash

验收标准：任何 Production Decision 都能反查
    decision → release → evidence pack；
缺少 Evidence Pack → NOT CERTIFIED。
"""

import hashlib
import json


EVIDENCE_PACK_FIELDS = (
    "release_manifest", "validation_certificate", "pit_certificate",
    "oos_result", "ablation_result", "stress_result", "replay_result",
    "shadow_result", "governance_approval",
)


def production_evidence_pack(release_id, evidence: dict) -> dict:
    """evidence：{field: ref}；生成 evidence_hash，缺字段 → NOT CERTIFIED。"""
    missing = [f for f in EVIDENCE_PACK_FIELDS
               if not evidence.get(f)]
    raw = json.dumps({k: evidence.get(k) for k in EVIDENCE_PACK_FIELDS},
                     sort_keys=True, ensure_ascii=False, default=str)
    evidence_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return {
        "release_id": release_id,
        "evidence_hash": evidence_hash,
        "components": {k: evidence.get(k) for k in EVIDENCE_PACK_FIELDS},
        "missing": missing,
        "certified": not missing,
        "certification": "CERTIFIED" if not missing
        else "NOT_CERTIFIED",
        "chain": "decision → release → evidence pack",
    }


def trace_decision_to_evidence(decision_id, release_id,
                               pack: dict) -> dict:
    """反查：decision → release → evidence pack。"""
    return {
        "decision_id": decision_id,
        "release_id": release_id,
        "evidence_hash": pack.get("evidence_hash"),
        "certification": pack.get("certification"),
        "traceable": bool(pack.get("evidence_hash")),
    }


def evidence_pack_ledger_binding(decision_id, release_id,
                                 evidence_pack: dict) -> dict:
    """新 91 号：DecisionSnapshot.release_id + EvidencePackID +
    EvidenceHash 写入 Ledger 的可持久化记录。"""
    evidence_hash = (evidence_pack or {}).get("evidence_hash") or ""
    return {
        "ledger_record": {
            "decision_id": decision_id,
            "release_id": release_id,
            "evidence_pack_id": evidence_hash,
            "evidence_hash": evidence_hash,
            "certification": "CERTIFIED" if release_id and evidence_hash
            else "NOT_CERTIFIED",
        },
        "writable": bool(decision_id and release_id and evidence_hash),
        "rule": "任意 Production Decision 都必须反查到完整证据包",
    }


def decision_qualification_answer(decision_id, release_id,
                                  evidence_pack: dict) -> dict:
    """新 91 号：回答"这笔决策凭什么有资格被系统正式使用？"。"""
    bound = evidence_pack_ledger_binding(decision_id, release_id,
                                         evidence_pack)
    record = bound["ledger_record"]
    if record["certification"] == "NOT_CERTIFIED":
        return {"decision_id": decision_id,
                "qualification": "NOT_CERTIFIED",
                "reason": "无法反查 release_id/evidence_pack",
                "chain": "decision → release → evidence pack 断裂"}
    return {"decision_id": decision_id,
            "qualification": "CERTIFIED",
            "reason": f"release_id={release_id}，"
                      f"evidence_hash={record['evidence_hash']}",
            "chain": "decision → release → evidence pack"}
