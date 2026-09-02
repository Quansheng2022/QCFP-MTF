# coding: utf-8
"""Production Feature Manifest（QCFP-MTF 2.8：新 17 号）

把 FEATURE_SET 从"代码能力清单"改成真正的 Production Feature
Manifest：状态固定为
    DEFINED → WIRED → VALIDATED → CERTIFIED → ACTIVE → RETIRED
只有 ACTIVE 进入 ProductionManifestHash。

验收标准：DecisionSnapshot 的 feature manifest 只能包含这次真实
参与决策的 ACTIVE features；测试通过但未接线的模块不能出现在
Production capability 声明中。
"""

import hashlib
import json


FEATURE_STATES = ("DEFINED", "WIRED", "VALIDATED", "CERTIFIED",
                  "ACTIVE", "RETIRED")


def production_feature_manifest(feature_states: dict) -> dict:
    """feature_states：{feature: state}；只有 ACTIVE 进入 manifest。"""
    active = sorted(
        f for f, s in (feature_states or {}).items()
        if str(s or "").upper() == "ACTIVE")
    invalid = [f for f, s in (feature_states or {}).items()
               if str(s or "").upper() not in FEATURE_STATES]
    raw = json.dumps(active, ensure_ascii=False)
    return {
        "active_features": active,
        "active_count": len(active),
        "invalid_states": invalid,
        "production_manifest_hash": hashlib.sha256(
            raw.encode("utf-8")).hexdigest()[:16],
        "rule": "只有 ACTIVE 进入 ProductionManifestHash；"
                "测试通过但未接线 ≠ 生产能力",
    }


def participating_features(snapshot) -> list:
    """从真实 DecisionSnapshot 反推本次实际参与决策的 feature 路径。"""
    path = list(getattr(snapshot, "decision_path", ()) or ())
    mapped = {
        "evidence": "pit_evidence",
        "institutional": "institutional_permission",
        "exit_events": "hard_exit",
        "setup": "swing_setup",
        "participation_budget": "participation_budget",
        "fsm": "retail_fsm",
        "sizing": "retail_position_sizing",
        "permission_cap": "permission_policy",
        "trade_quality": "trade_quality",
        "governance": "governance_finalize",
        "final_target": "canonical_final_target",
    }
    return [mapped.get(s, s) for s in path if s in mapped]


def decision_participating_manifest(snapshot) -> dict:
    """Release 2（新 19 号）：Decision Participating Manifest——
    这一笔 Decision 真正经过哪些能力（不是全项目 371 个 Feature）。"""
    features = participating_features(snapshot)
    raw = json.dumps(features, ensure_ascii=False)
    return {
        "participating_features": features,
        "participating_hash": hashlib.sha256(
            raw.encode("utf-8")).hexdigest()[:16],
        "count": len(features),
        "rule": "DEFINED + test PASS 但没有真实接线 ≠ Production capability",
    }


def decision_identity_hash(release_manifest_hash, participating_hash) -> str:
    """DecisionHash 引用 ReleaseManifestHash + ParticipatingFeatureHash。"""
    raw = json.dumps({"release": release_manifest_hash,
                      "participating": participating_hash},
                     sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
