# coding: utf-8
"""Change Impact Classification（流程治理 Sprint B #6）

复用已有 change_impact.py 基础，把影响面正式收敛为三档：
    LOW       → Static + Unit + Relevant Regression
    STANDARD  → Static + Unit + Integration + Golden + Invariant
                + Architecture Conformance
    HIGH      → Full Regression + Golden + Replay + PIT + OOS + Ablation
                + Stress + Failure Injection + Architecture Authority Audit
                + Shadow + Human Review

入口规则（QCFP-SPEC-CHG-001）：
    任何代码任务没有 Change Impact → 不能生成 Implementation Contract。
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone

from .change_impact import change_impact_matrix


HIGH_CRITICAL_AREAS = (
    "PIT", "Permission", "HardExit", "FinalTarget", "CanonicalAuthority",
    "DecisionSchema", "ReleaseIdentity", "ValidationAuthority",
    "LedgerIntegrity",
)

REQUIRED_VALIDATION = {
    "LOW": ("static", "unit", "relevant_regression"),
    "STANDARD": ("static", "unit", "integration", "golden", "invariant",
                 "architecture_conformance"),
    "HIGH": ("full_regression", "golden", "replay", "pit", "oos",
             "ablation", "stress", "failure_injection",
             "architecture_authority_audit", "shadow", "human_review"),
}

# C2：关键文件 → 观察到的关键面（Observed Diff Impact）
OBSERVED_CRITICAL_FILE_MAP = {
    "decision/schema": "DecisionSchema",
    "decision/schema_registry": "DecisionSchema",
    "decision/schema_contract": "DecisionSchema",
    "decision/governance": "FinalTarget",
    "decision/canonical_action": "FinalTarget",
    "decision/institutional_permission": "Permission",
    "institutional/permission": "Permission",
    "decision/permission_policy": "Permission",
    "data/pit_registry": "PIT",
    "data/asof_contract": "PIT",
    "decision/hard_exit": "HardExit",
    "decision/decision_ledger": "LedgerIntegrity",
    "decision/release_identity": "ReleaseIdentity",
    "decision/decision_snapshot": "DecisionSchema",
    "governance/validation_certificate": "ValidationAuthority",
}

# SF-1：Observed Diff Evidence 契约与状态
OBSERVED_DIFF_SCHEMA = "OBSERVED-DIFF-2"

CHANGE_IMPACT_READY = "CHANGE_IMPACT_READY"
CHANGE_IMPACT_NOT_PROVEN = "CHANGE_IMPACT_NOT_PROVEN"
CHANGE_IMPACT_INVALID = "CHANGE_IMPACT_INVALID"
CHANGE_IMPACT_NO_CHANGE = "CHANGE_IMPACT_NO_CHANGE"


def _sha256(obj) -> str:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def observe_diff_impact(changed_files, critical_file_map=None) -> dict:
    """Observed Diff Impact：从真实 diff 文件推导 critical areas / tier。

    只允许升级（effective_tier = max(declared, observed)），
    不允许调用者用观察结果自行降级。
    """
    critical_file_map = critical_file_map or OBSERVED_CRITICAL_FILE_MAP
    observed_critical = set()
    for f in changed_files or []:
        norm = str(f).replace("\\", "/")
        for key, area in critical_file_map.items():
            if key in norm:
                observed_critical.add(area)
    if observed_critical:
        observed_tier = "HIGH"
    elif changed_files:
        observed_tier = "STANDARD"
    else:
        observed_tier = "LOW"
    return {"observed_critical_areas": sorted(observed_critical),
            "observed_tier": observed_tier}


def validate_observed_diff(diff) -> dict:
    """OBSERVED-DIFF-2 契约校验（SF-1）。

    * diff 缺失 / schema 非法 / diff_hash 缺失 / 字段缺失 → NOT_PROVEN
    * empty changed_files + source == target → NO_CHANGE（有效，无变更）
    * empty changed_files + source != target → NOT_PROVEN（空证据旁路）
    """
    if diff is None:
        return {"status": CHANGE_IMPACT_NOT_PROVEN,
                "reason": "Observed Diff Evidence 缺失：Production Change "
                          "Impact 必须建立在 Declared + Observed 两套事实之上"}
    if not isinstance(diff, dict):
        return {"status": CHANGE_IMPACT_NOT_PROVEN,
                "reason": "Observed Diff 非法"}
    if diff.get("schema") != OBSERVED_DIFF_SCHEMA:
        return {"status": CHANGE_IMPACT_NOT_PROVEN,
                "reason": f"Observed Diff schema != {OBSERVED_DIFF_SCHEMA}"}
    if not diff.get("diff_hash"):
        return {"status": CHANGE_IMPACT_NOT_PROVEN,
                "reason": "diff_hash 缺失"}
    if not isinstance(diff.get("changed_files"), list):
        return {"status": CHANGE_IMPACT_NOT_PROVEN,
                "reason": "changed_files 缺失或非法"}
    source = diff.get("source_commit")
    target = diff.get("target_commit")
    if not source or not target:
        return {"status": CHANGE_IMPACT_NOT_PROVEN,
                "reason": "source_commit/target_commit 缺失"}
    if not diff["changed_files"]:
        if source == target:
            return {"status": CHANGE_IMPACT_NO_CHANGE,
                    "reason": "empty changed_files + source==target → 无变更"}
        return {"status": CHANGE_IMPACT_NOT_PROVEN,
                "reason": "empty changed_files 但 source != target → "
                          "空证据旁路，NOT_PROVEN"}
    return {"status": CHANGE_IMPACT_READY,
            "reason": "Observed Diff Evidence 有效"}


def classify_change(change: dict) -> dict:
    """change: {change_type, description, touches: [...], critical_areas: [...]}

    兼容已有 change_impact_matrix 的 touches 判定，并显式识别 HIGH 关键面。
    """
    matrix = change_impact_matrix(change)
    touches = set(change.get("touches") or ())
    critical = set(change.get("critical_areas") or ()) \
        | touches & set(HIGH_CRITICAL_AREAS)
    if critical:
        tier = "HIGH"
    elif matrix["affected_areas"] and matrix["release_track"] == "STANDARD":
        tier = "STANDARD"
    else:
        tier = "LOW"
    return {
        "change_type": change.get("change_type"),
        "change_id": change.get("change_id", ""),
        "description": change.get("description", ""),
        "affected_areas": matrix["affected_areas"],
        "critical_areas": sorted(critical),
        "tier": tier,
        "validation_requirements": list(REQUIRED_VALIDATION[tier]),
        "validation_requirement": "FULL_VALIDATION" if tier == "HIGH"
        else "STANDARD_VALIDATION" if tier == "STANDARD" else "LOW",
        "release_gate": "CHANGE_IMPACT_GATE",
        "rule": "HIGH 必须 Full Regression + Golden + Replay + PIT + OOS "
                "+ Ablation + Stress + Failure Injection + Authority Audit "
                "+ Shadow + Human Review",
    }


def change_impact_entry_rule(impact: dict = None, change: dict = None) -> dict:
    """入口规则：没有 Change Impact → 不能生成 Implementation Contract。"""
    if impact is None and change is not None:
        impact = classify_change(change)
    if not impact:
        return {"gate": "CHANGE_IMPACT_GATE",
                "verdict": "NO_CHANGE_IMPACT",
                "pass": False,
                "rule": "任何代码任务没有 Change Impact → "
                        "不能生成 Implementation Contract"}
    return {"gate": "CHANGE_IMPACT_GATE",
            "verdict": "IMPACT_RECORDED",
            "pass": True,
            "tier": impact.get("tier"),
            "validation_requirements": impact.get("validation_requirements"),
            "rule": "只有先记录 Change Impact 才能进入 Implementation "
                    "Contract"}


def change_impact_record(change: dict, diff_evidence=None) -> dict:
    """生成 CHANGE-IMPACT-2 记录（供 Contract 前置使用）。"""
    impact = effective_change_impact(change, diff_evidence)
    impact["schema"] = "CHANGE-IMPACT-2"
    impact["change_hash"] = _sha256(change)
    impact["source_commit"] = (diff_evidence or {}).get("source_commit") \
        or change.get("source_commit", "")
    impact["generated_at"] = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    # SF-1：approved_for_contract 由程序计算，不由输入 JSON 声明
    impact["approved_for_contract"] = bool(
        impact["status"] == CHANGE_IMPACT_READY
        and impact.get("tier") in ("LOW", "STANDARD", "HIGH")
        and bool(change.get("change_id"))
        and bool(impact.get("change_hash")))
    record = {
        "record": "CHANGE_IMPACT_RECORD",
        "impact": impact,
        "entry_rule": change_impact_entry_rule(impact=impact),
        "gate": "CHANGE_IMPACT_GATE",
        "rule": "Contract 必须绑定 change_impact.json：change_id / tier / "
                "change_hash 任一不一致 → CONTRACT_INVALID",
    }
    return record


def effective_change_impact(change: dict, diff_evidence=None) -> dict:
    """Declared Impact + Observed Diff Impact = Effective Impact（SF-1）。

    * Observed Diff 缺失/非法 → CHANGE_IMPACT_NOT_PROVEN（≠ LOW）
    * effective_tier = max(declared, observed)，只允许升级，不允许自动降级。
    """
    declared = classify_change(change)
    diff_check = validate_observed_diff(diff_evidence)
    if diff_check["status"] not in (CHANGE_IMPACT_READY,
                                    CHANGE_IMPACT_NO_CHANGE):
        effective = dict(declared)
        effective["status"] = diff_check["status"]
        effective["reason"] = diff_check["reason"]
        effective["declared_tier"] = declared["tier"]
        effective["observed_tier"] = None
        effective["approved_for_contract"] = False
        return effective
    observed = observe_diff_impact(
        (diff_evidence or {}).get("changed_files") or [])
    tier_order = {"LOW": 0, "STANDARD": 1, "HIGH": 2}
    effective_tier = max(
        (declared["tier"], observed["observed_tier"]),
        key=lambda t: tier_order[t])
    effective = dict(declared)
    effective["tier"] = effective_tier
    effective["declared_tier"] = declared["tier"]
    effective["observed_tier"] = observed["observed_tier"]
    effective["observed_critical_areas"] = \
        observed["observed_critical_areas"]
    effective["critical_areas"] = sorted(
        set(declared["critical_areas"])
        | set(observed["observed_critical_areas"]))
    effective["validation_requirements"] = list(
        REQUIRED_VALIDATION[effective_tier])
    effective["validation_requirement"] = \
        "FULL_VALIDATION" if effective_tier == "HIGH" else \
        "STANDARD_VALIDATION" if effective_tier == "STANDARD" else "LOW"
    effective["status"] = diff_check["status"]
    effective["diff_status"] = diff_check["status"]
    effective["observed_diff_valid"] = True
    effective["approved_for_contract"] = bool(change.get("change_id"))
    return effective


def write_change_impact_record(change: dict, out_path,
                               diff_evidence=None) -> dict:
    record = change_impact_record(change, diff_evidence)
    # artifact 顶层即 CHANGE-IMPACT-2 impact（Judge 直接消费）
    Path(out_path).write_text(
        json.dumps(record["impact"], ensure_ascii=False, indent=2),
        encoding="utf-8")
    return record
