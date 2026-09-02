# coding: utf-8
"""Implementation Contract（流程治理 Sprint B #4）

把「Implementation Plan → DeepSeek」升级为「Implementation Contract →
DeepSeek Builder」。Contract 冻结：
    * Allowed Change Surface（可改文件 / 可新增文件 / 可删除文件）
    * Protected Surface（禁止文件 / 禁止新增 Authority / 禁止新增功能）
    * Expected Behavior Change 与 Expected Unchanged Behavior（同样重要）

DoD：DeepSeek patch 完成后 git diff → Contract Scope Checker；
出现计划外文件 / 计划外 Authority / 计划外 Schema / 计划外 Production
Feature → SCOPE_VIOLATION，不得直接进入测试。

规则：QCFP-SPEC-CHG-001/002。
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from .traceability import load_yaml_file


CONTRACT_PATH = Path(__file__).resolve().parent / "implementation_contract.yaml"

REQUIRED_FIELDS = (
    "change_id", "objective", "spec_ids", "change_type",
    "change_impact_artifact", "change_impact_hash", "change_tier",
    "allowed_files", "forbidden_files", "authorities_touched",
    "expected_behavior_change", "expected_unchanged_behavior",
    "acceptance_criteria",
)

OPTIONAL_FIELDS = (
    "adr_ids", "allowed_new_files", "files_to_delete",
    "schema_change", "permission_change", "final_target_change",
    "pit_change", "required_tests", "required_negative_tests",
    "required_failure_injection", "required_ablation", "required_oos",
    "required_shadow", "complexity_budget", "retirement_effect",
)


def contract_template() -> dict:
    """Contract 模板（与计划字段一致）。"""
    return {
        "change_id": "",
        "objective": "",
        "spec_ids": [],
        "adr_ids": [],
        "change_type": "",
        "change_impact_artifact": "",
        "change_impact_hash": "",
        "change_tier": "",
        "allowed_files": [],
        "allowed_new_files": [],
        "files_to_delete": [],
        "forbidden_files": [],
        "authorities_touched": [],
        "expected_behavior_change": "",
        "expected_unchanged_behavior": "",
        "schema_change": False,
        "permission_change": False,
        "final_target_change": False,
        "pit_change": False,
        "required_tests": [],
        "required_negative_tests": [],
        "required_failure_injection": [],
        "required_ablation": [],
        "required_oos": [],
        "required_shadow": [],
        "complexity_budget": "",
        "retirement_effect": "",
        "acceptance_criteria": [],
    }


def load_contract(path=None) -> dict:
    data = load_yaml_file(path or CONTRACT_PATH)
    return data if isinstance(data, dict) else {}


def validate_implementation_contract(contract: dict) -> dict:
    """Contract 完整性校验（缺必填 → CONTRACT_INVALID）。"""
    errors = []
    for field in REQUIRED_FIELDS:
        value = contract.get(field)
        if isinstance(value, str):
            missing = not value.strip()
        elif isinstance(value, list):
            missing = field in ("spec_ids", "acceptance_criteria") \
                and not value
        else:
            missing = value in (None, {})
        if missing:
            errors.append(f"missing required field: {field}")
    for field in ("spec_ids", "allowed_files", "forbidden_files",
                  "authorities_touched", "acceptance_criteria"):
        value = contract.get(field)
        if value is not None and not isinstance(value, list):
            errors.append(f"{field} must be a list")
    critical = (contract.get("permission_change")
                or contract.get("final_target_change")
                or contract.get("pit_change")
                or contract.get("schema_change"))
    if critical and not contract.get("spec_ids"):
        errors.append("critical change requires spec_ids")
    tier = contract.get("change_tier")
    if tier not in (None, "", "LOW", "STANDARD", "HIGH"):
        errors.append(f"invalid change_tier: {tier!r}")
    return {
        "change_id": contract.get("change_id"),
        "errors": errors,
        "valid": not errors,
        "verdict": "CONTRACT_VALID" if not errors
        else "CONTRACT_INVALID",
        "critical_change": bool(critical),
    }


def bind_change_impact(contract: dict, impact: dict) -> dict:
    """C2：Contract 必须绑定 Change Impact Artifact。

    校验（任一不一致 → CONTRACT_INVALID）：
        contract.change_id == impact.change_id
        contract.change_tier == impact.tier
        contract.change_impact_hash == hash(impact)
    """
    if not impact:
        return {"bound": False,
                "verdict": "CONTRACT_INVALID",
                "errors": ["没有 Change Impact Artifact，禁止生成 Contract"
                           "（QCFP-SPEC-CHG-001）"]}
    impact_flat = dict(impact)
    impact_hash = impact_flat.get("change_hash")
    mismatches = []
    if contract.get("change_id") != impact_flat.get("change_id"):
        mismatches.append("change_id mismatch")
    if contract.get("change_tier") != impact_flat.get("tier"):
        mismatches.append("change_tier mismatch")
    if contract.get("change_impact_hash") != impact_hash:
        mismatches.append("change_impact_hash mismatch")
    if not impact_flat.get("approved_for_contract", False):
        mismatches.append("impact not approved_for_contract")
    return {
        "bound": not mismatches,
        "change_id": contract.get("change_id"),
        "impact_tier": impact_flat.get("tier"),
        "mismatches": mismatches,
        "verdict": "CONTRACT_BOUND" if not mismatches
        else "CONTRACT_INVALID",
        "rule": "Contract.change_id == impact.change_id；"
                "change_tier == impact.tier；"
                "change_impact_hash == hash(impact)；"
                "任一不一致 → CONTRACT_INVALID",
    }


def contract_result_artifact(contract: dict, gate_result: dict,
                             out_dir) -> dict:
    """写 implementation_contract_result.json（C7 必需 artifact）。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "schema": "CONTRACT-RESULT-2",
        "change_id": contract.get("change_id"),
        "change_tier": contract.get("change_tier"),
        "change_impact_hash": contract.get("change_impact_hash"),
        "verdict": gate_result.get("verdict"),
        "violations": gate_result.get("violations", []),
        "generated_at": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "pass": gate_result.get("pass", False),
    }
    (out_dir / "implementation_contract_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8")
    return result


def check_change_surface(contract: dict, changed_files) -> dict:
    """Contract Scope Checker：git diff 与 Contract 比对。

    changed_files: iterable of changed file paths（相对项目根）。
    任一项越界 → SCOPE_VIOLATION。
    """
    validation = validate_implementation_contract(contract)
    changed = set(str(f).replace("\\", "/") for f in (changed_files or ()))
    allowed = set(contract.get("allowed_files") or ())
    allowed_new = set(contract.get("allowed_new_files") or ())
    to_delete = set(contract.get("files_to_delete") or ())
    forbidden = set(contract.get("forbidden_files") or ())
    out_of_scope = []
    for f in sorted(changed):
        in_allowed = any(f == a or f.startswith(a.rstrip("/") + "/")
                         for a in allowed)
        in_new = any(f == n or f.startswith(n.rstrip("/") + "/")
                     for n in allowed_new)
        if not (in_allowed or in_new):
            out_of_scope.append(f)
    forbidden_touched = sorted(f for f in changed
                               if f in forbidden
                               or any(f.startswith(x.rstrip("/") + "/")
                                      for x in forbidden))
    undeclared_delete = sorted(f for f in to_delete if f not in changed)
    violations = []
    if out_of_scope:
        violations.append({"kind": "FILE_SCOPE",
                           "detail": out_of_scope})
    if forbidden_touched:
        violations.append({"kind": "PROTECTED_SURFACE",
                           "detail": forbidden_touched})
    if undeclared_delete:
        violations.append({"kind": "UNDECLARED_DELETE",
                           "detail": undeclared_delete})
    if not validation["valid"]:
        violations.append({"kind": "CONTRACT_INVALID",
                           "detail": validation["errors"]})
    return {
        "change_id": contract.get("change_id"),
        "changed_files": sorted(changed),
        "violations": violations,
        "verdict": "CONTRACT_OK" if not violations
        else "SCOPE_VIOLATION",
        "rule": "计划外文件 / 计划外 Authority / 计划外 Schema / "
                "计划外 Production Feature → SCOPE_VIOLATION，"
                "不得直接进入测试",
        "expected_unchanged_behavior": contract.get(
            "expected_unchanged_behavior"),
    }


def implementation_contract_gate(contract: dict, changed_files) -> dict:
    result = check_change_surface(contract, changed_files)
    return {
        "gate": "IMPLEMENTATION_CONTRACT_GATE",
        "verdict": "CONTRACT_OK" if result["verdict"] == "CONTRACT_OK"
        else "SCOPE_VIOLATION",
        "pass": result["verdict"] == "CONTRACT_OK",
        "violations": result["violations"],
    }
