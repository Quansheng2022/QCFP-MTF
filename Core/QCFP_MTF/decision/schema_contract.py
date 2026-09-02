# coding: utf-8
"""DecisionSchemaContract（QCFP-MTF 2.8：41 号 Schema 契约与迁移规则）

字段分类：REQUIRED / OPTIONAL / DEPRECATED / FORBIDDEN
旧 Snapshot 判定：可直接 Replay / 需要 Migration / 不可 Replay
（不能静默兼容）。
"""


SCHEMA_FIELD_STATUS = {
    "decision_id": "REQUIRED",
    "stock_code": "REQUIRED",
    "decision_date": "REQUIRED",
    "institutional_permission": "REQUIRED",
    "wave_stage": "REQUIRED",
    "binding_constraint": "REQUIRED",
    # Release 3（新 21 号）：核心身份正式纳入 REQUIRED
    "release_id": "REQUIRED",
    "release_manifest_hash": "REQUIRED",
    "decision_path_hash": "REQUIRED",
    "canonical_action": "REQUIRED",
    "wave_proposal_target": "REQUIRED",
    "target_position": "REQUIRED",
    "previous_position": "REQUIRED",
    "raw_target_position": "REQUIRED",
    "next_fsm_state": "REQUIRED",
    "primary_reason": "REQUIRED",
    "context": "REQUIRED",
    "legacy_target": "DEPRECATED",
    "legacy_action_signal": "FORBIDDEN",
    "legacy_position": "DEPRECATED",
    "future_return": "FORBIDDEN",
    "wave_label": "FORBIDDEN",
    "realized_mfe": "FORBIDDEN",
    "capture_ratio": "FORBIDDEN",
    "decision_hash": "OPTIONAL",
    "run_id": "OPTIONAL",
}


def schema_contract(version, fields: dict) -> dict:
    """校验快照字段符合 Schema 契约。"""
    violations = []
    missing_required = []
    forbidden_present = []
    for name, status in SCHEMA_FIELD_STATUS.items():
        if status == "REQUIRED" and name not in fields:
            missing_required.append(name)
        elif status == "FORBIDDEN" and name in fields \
                and fields[name] is not None:
            forbidden_present.append(name)
    if missing_required:
        violations.append(f"MISSING_REQUIRED:{missing_required}")
    if forbidden_present:
        violations.append(f"FORBIDDEN_PRESENT:{forbidden_present}")
    return {"schema_version": version, "valid": not violations,
            "violations": violations,
            "missing_required": missing_required,
            "forbidden_present": forbidden_present}


def snapshot_replayability(version, fields: dict) -> dict:
    """旧 Snapshot 判定：REPLAY / MIGRATE / NOT_REPLAYABLE。"""
    contract = schema_contract(version, fields)
    forbidden = contract["forbidden_present"]
    if forbidden or not contract["valid"] and "MISSING_REQUIRED" in \
            " ".join(contract["violations"]):
        # 缺 REQUIRED → 需迁移；含 FORBIDDEN → 不可回放
        if forbidden:
            return {"verdict": "NOT_REPLAYABLE",
                    "reason": f"含 forbidden 字段 {forbidden}"}
        return {"verdict": "MIGRATE",
                "reason": "缺 REQUIRED 字段"}
    return {"verdict": "REPLAY", "reason": "可直接回放"}


# 新 41 号：显式 Schema Migration（禁止 silent fallback）
SCHEMA_MIGRATIONS = {
    "DECISION-1.1": "DECISION-1.2",
    "DECISION-1.2": "DECISION-1.3",
}


def schema_migration_rule(from_version, to_version) -> dict:
    """查询显式迁移规则。"""
    expected = SCHEMA_MIGRATIONS.get(from_version)
    if expected is None or expected != to_version:
        return {"from": from_version, "to": to_version,
                "migration": None, "migration_defined": False}
    return {"from": from_version, "to": to_version,
            "migration": expected, "migration_defined": True,
            "next_version": expected}


def schema_change_release_gate(from_version, to_version) -> dict:
    """新 41 号：Schema 变化没有 Migration/Compatibility Rule
    → Release REJECTED。"""
    rule = schema_migration_rule(from_version, to_version)
    if not rule["migration_defined"]:
        return {"verdict": "RELEASE_REJECTED",
                "reason": f"{from_version} 无迁移规则（Schema 兼容不能靠猜）",
                "allowed": False}
    return {"verdict": "RELEASE_ALLOWED",
            "reason": f"{from_version} → {rule['migration']} "
                      "已定义显式迁移",
            "allowed": True}


def schema_release_hard_gate(version, fields, from_version=None,
                             migration_exists=None) -> dict:
    """Release 3（新 21 号）：Schema Contract 正式发布门。

    Schema unchanged → DIRECT_REPLAY
    Schema changed + migration exists → MIGRATION_REQUIRED → PASS
    Schema changed + no migration → RELEASE_REJECTED
    FORBIDDEN future-aware field exists → NOT_REPLAYABLE
    """
    contract = schema_contract(version, fields)
    if contract["forbidden_present"]:
        return {"verdict": "NOT_REPLAYABLE",
                "forbidden": contract["forbidden_present"],
                "allowed": False,
                "rule": "FORBIDDEN future-aware 字段存在 → 不可回放"}
    if from_version and from_version != version:
        if not migration_exists:
            return {"verdict": "RELEASE_REJECTED",
                    "reason": f"{from_version} → {version} 无显式迁移",
                    "allowed": False}
        return {"verdict": "MIGRATION_REQUIRED",
                "reason": "Schema 变化但已有显式迁移 → PASS",
                "allowed": True}
    replay = snapshot_replayability(version, fields)
    if replay["verdict"] != "REPLAY":
        return {"verdict": "MIGRATION_REQUIRED",
                "reason": "旧快照需迁移",
                "allowed": True}
    return {"verdict": "DIRECT_REPLAY", "allowed": True}
