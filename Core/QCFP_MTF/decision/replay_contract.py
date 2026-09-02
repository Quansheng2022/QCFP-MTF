# coding: utf-8
"""DecisionReplayContract（QCFP-MTF 2.8：21 号决策回放契约）

Replay 目标：相同证据 + 相同版本 + 相同配置 → 相同决策。

    DecisionReplayInput
    ├─ EvidenceSnapshotID / StrategyVersion / EngineVersion /
    │  GovernanceRuleVersion / ConfigHash / FeatureManifestHash /
    │  UniverseSnapshotID / RandomSeed
    └─ 输出：Original/Replay DecisionHash / ExactMatch / MismatchFields

区分四类回放：Data / Decision / Execution / Research。

职责边界（MTR Q4 Closure）：
    decision_ledger.py   = What happened?（事实追加/不可变持久化/链）
    replay_contract.py   = Can it be reconstructed?（Replay 材料校验/
                           Settings Blob/引用可解析/Eligibility）
    replay_engine.py     = Does reconstruction produce same decision?

本模块是 Production reachable supporting module：
    Authority = NONE / FinalTarget writer = NO /
    CanonicalAction writer = NO / Permission writer = NO。
"""

import json
from dataclasses import asdict, dataclass, field

from .decision_snapshot import _settings_hash


def _sg(obj, key, default=None):
    """同时兼容 DecisionSnapshot 对象与 Ledger 行 dict。"""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def replay_eligibility(conn, snap, resolve_references=False,
                       resolvable_data_ids=None,
                       resolvable_universe_ids=None) -> dict:
    """Replayability Gate（Q8-R1）：完整 Replay Material 校验。

    settings_hash → settings_blob 必须**真正 JSON parse 成功**
    **且 canonical 序列化哈希一致**（不是只有一行记录）；
    release/model/rule/schema/data/universe/input/prev 状态/
    decision_path/path_hash/manifest 全部可找回。
    resolve_references=True（正式 Replay Gate）时，data/universe
    snapshot 必须证明未来能找回（引用可解析）。
    任一缺失 → replay_eligible=False（不阻止记录，阻止 Certification）。

    MTR Q4：本校验属于 Replay Contract，不属于 Decision Ledger 的
    事实 Authority——Ledger 只消费本函数的结论。"""
    ctx = _sg(snap, "context", None) or {}
    _release_identity = (ctx.get("release_identity") or {})
    settings_ok = False
    settings_reason = ""
    settings_hash = _sg(snap, "settings_hash", "") or ""
    if settings_hash:
        try:
            row = conn.execute(
                "SELECT settings_blob FROM qcfp_model_registry "
                "WHERE settings_hash=? LIMIT 1", (settings_hash,)).fetchone()
            if row is None:
                settings_reason = "SETTINGS_NOT_REGISTERED"
            elif not row["settings_blob"]:
                settings_reason = "SETTINGS_EMPTY"
            else:
                try:
                    parsed = json.loads(row["settings_blob"])
                except Exception:
                    settings_reason = "SETTINGS_UNPARSABLE"
                else:
                    if isinstance(parsed, dict) \
                            and _settings_hash(parsed) == settings_hash:
                        settings_ok = True
                    else:
                        settings_reason = "SETTINGS_HASH_MISMATCH"
        except Exception:
            settings_ok = False
    missing = []
    if not settings_ok:
        missing.append(f"settings_blob({settings_reason or 'UNRESOLVABLE'})")
    if not _sg(snap, "decision_id", ""):
        missing.append("decision_id")
    if not _sg(snap, "input_fingerprint", ""):
        missing.append("input_fingerprint")
    if not _sg(snap, "release_id", "") \
            and not _release_identity.get("release_id"):
        missing.append("release_id")
    if not _sg(snap, "model_version", ""):
        missing.append("model_version")
    if not _sg(snap, "rule_version", ""):
        missing.append("rule_version")
    if not _sg(snap, "schema_version", ""):
        missing.append("schema_version")
    data_snap = _sg(snap, "data_snapshot_id", "") or \
        _release_identity.get("data_snapshot_id") or ""
    universe_snap = _sg(snap, "universe_snapshot_id", "") or \
        _release_identity.get("universe_snapshot_id") or ""
    if not data_snap:
        missing.append("data_snapshot_id")
    elif resolve_references and data_snap not in (resolvable_data_ids
                                                  or set()):
        missing.append("data_snapshot_id(UNRESOLVABLE)")
    if not universe_snap:
        missing.append("universe_snapshot_id")
    elif resolve_references and universe_snap not in (
            resolvable_universe_ids or set()):
        missing.append("universe_snapshot_id(UNRESOLVABLE)")
    if not _sg(snap, "prev_fsm_state", ""):
        missing.append("prev_fsm_state")
    if _sg(snap, "previous_position", None) is None:
        missing.append("previous_position")
    if not _sg(snap, "decision_path", ()):
        missing.append("decision_path")
    if not ctx.get("decision_path_hash"):
        missing.append("decision_path_hash")
    if not _sg(snap, "production_manifest_hash", "") \
            and not ctx.get("production_manifest_hash") \
            and not _release_identity.get("production_manifest_hash"):
        missing.append("production_manifest_hash")
    if not _sg(snap, "participating_feature_hash", "") \
            and not ctx.get("participating_feature_hash"):
        missing.append("participating_feature_hash")
    return {"replay_eligible": not missing,
            "missing": missing,
            "settings_hash": settings_hash,
            "settings_resolvable": settings_ok,
            "settings_reason": settings_reason,
            "rule": "settings 不能只存 Hash——settings_blob 必须真正 "
                    "JSON parse 成功且 canonical hash 一致；完整 Replay "
                    "material 缺失/不可解析 → replay_eligible=False"}


@dataclass(frozen=True)
class DecisionReplayInput:
    evidence_snapshot_id: str
    strategy_version: str = ""
    engine_version: str = ""
    governance_rule_version: str = ""
    config_hash: str = ""
    feature_manifest_hash: str = ""
    universe_snapshot_id: str = ""
    random_seed: int = 0
    replay_type: str = "decision"    # data/decision/execution/research

    def as_dict(self) -> dict:
        return asdict(self)


def replay_types() -> tuple:
    return ("data", "decision", "execution", "research")


def decision_replay_contract(input_spec: DecisionReplayInput,
                             original_decision_hash, replay_decision_hash,
                             mismatch_fields=None) -> dict:
    """回放契约认证。"""
    exact = (original_decision_hash == replay_decision_hash
             and not mismatch_fields)
    return {
        "replay_input": input_spec.as_dict(),
        "original_decision_hash": original_decision_hash,
        "replay_decision_hash": replay_decision_hash,
        "exact_match": bool(exact),
        "mismatch_fields": list(mismatch_fields or ()),
        "certified": exact,
        "production_ok": exact and input_spec.replay_type in (
            "decision", "data"),
    }


def assert_replay_certified(contract: dict) -> None:
    """Production Certification：decision_hash(original) ==
    decision_hash(replay)，否则失败。"""
    if not contract.get("exact_match"):
        from .replay_cert import ReplayCert
        raise ValueError(
            f"ReplayContract: 不一致 "
            f"({contract.get('original_decision_hash')} vs "
            f"{contract.get('replay_decision_hash')}) "
            f"mismatch={contract.get('mismatch_fields')}")
