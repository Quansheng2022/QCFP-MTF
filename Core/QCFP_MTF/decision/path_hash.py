# coding: utf-8
"""Decision Path Hash（QCFP-MTF 2.8：34 号决策路径指纹）

把整条决策链共同哈希：
    Data + Feature Set + Permission + Wave + FSM + Risk + Portfolio +
    Execution + Governance → decision_path_hash

用途：Input Hash 一致但 Path Hash 不一致 → 同一输入经过了不同的决策逻辑
（隐藏版本漂移检测）。
"""

import hashlib
import json


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def decision_path_hash(snap) -> str:
    """决策路径指纹（snap：DecisionSnapshot 或 dict）。"""
    ctx = _get(snap, "context") or {}
    parts = {
        "data": _get(snap, "input_fingerprint") or "",
        "features": _get(snap, "feature_manifest_hash") or "",
        "permission": _get(snap, "institutional_permission") or "",
        "wave": _get(snap, "setup_type") or "",
        "fsm": f"{_get(snap, 'prev_fsm_state')}->"
               f"{_get(snap, 'next_fsm_state')}",
        "risk": _get(snap, "exit_event_kind") or "",
        "portfolio": f"{_get(snap, 'participation_mode')}"
                     f"@{_get(snap, 'participation_cap')}",
        "execution": (ctx.get("execution_assumption")
                      if isinstance(ctx, dict) else "") or "T+1",
        "governance": (ctx.get("governance_proof") or {}).get("proof")
        if isinstance(ctx, dict) else "",
    }
    # 新 45 号：真正 Binding Caps 与版本身份纳入 PathHash
    for cap in ("permission_cap", "risk_cap", "portfolio_cap",
                "sector_cap", "theme_cap", "liquidity_cap",
                "execution_cap", "drawdown_cap"):
        parts[f"cap:{cap}"] = _get(snap, cap) or \
            ((ctx.get("governance_caps") or {}).get(cap)
             if isinstance(ctx, dict) else None)
    parts["binding_constraint"] = _get(snap, "binding_constraint") or ""
    parts["engine_version"] = _get(snap, "model_version") or ""
    parts["governance_rule_version"] = _get(snap, "rule_version") or ""
    parts["config_hash"] = _get(snap, "settings_hash") or ""
    # Release 2（新 13 号）：Wave 身份 + FinalTarget + CanonicalAction +
    # Release/Evidence/Data/Universe 身份全部纳入
    parts["wave_id"] = _get(snap, "wave_id") or ""
    parts["wave_stage"] = _get(snap, "wave_stage") or ""
    parts["wave_strength"] = _get(snap, "wave_strength") or 0.0
    parts["wave_proposal_target"] = _get(snap, "wave_proposal_target") or 0.0
    parts["final_target"] = _get(snap, "target_position") or 0.0
    parts["canonical_action"] = _get(snap, "canonical_action") or ""
    parts["release_id"] = _get(snap, "release_id") or ""
    parts["release_manifest_hash"] = _get(snap, "release_manifest_hash") or ""
    parts["evidence_pack_hash"] = _get(snap, "evidence_pack_hash") or ""
    parts["data_snapshot_id"] = _get(snap, "data_snapshot_id") or ""
    parts["universe_snapshot_id"] = _get(snap, "universe_snapshot_id") or ""
    raw = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def path_hash_determinism_check(identity_a: dict, hash_a: str,
                                identity_b: dict, hash_b: str) -> dict:
    """新 45 号：
        - 输入相同但治理配置不同 → PathHash 必须不同；
        - 所有 identity 相同却 PathHash 不同 → DETERMINISM FAILURE。"""
    same_identity = identity_a == identity_b
    if not same_identity and hash_a == hash_b:
        return {"verdict": "PATH_HASH_DRIFT",
                "reason": "输入/配置不同但 PathHash 相同（未捕获配置漂移）",
                "ok": False}
    if same_identity and hash_a != hash_b:
        return {"verdict": "DETERMINISM_FAILURE",
                "reason": "identity 相同但 PathHash 不同",
                "ok": False}
    return {"verdict": "CONSISTENT",
            "reason": "identity 与 PathHash 一致",
            "ok": True}
