# coding: utf-8
"""DeepSeek Patch Scope Lock（流程治理 Sprint C #8 + FGC-1 C4 + SF-2）

流程：
    Diff Evidence Generator → patch_evidence.json（PATCH-EVIDENCE-2）
        → Patch Scope Judge

SF-2 独立验证原则：
    * Patch Audit 回答「Deterministic Diff Evidence 证明它改了什么」，
      而不是「Builder 告诉我它改了什么」。
    * No Actual Evidence ≠ No Change；缺 patch_evidence /
      authority_graph before/after / feature manifest after
      → PATCH_NOT_PROVEN（不 fallback self-report）。
    * Patch Evidence 中只能出现 Observed Facts；出现 expected /
      allowed / approved → 无效（被审对象不得影响裁判预期）。
    * Authority Diff = graph-derived；Feature Diff = manifest-derived；
      Schema Diff = hash-derived；Golden Diff = comparator-derived。

Self Report Authority = 0（Production 禁止 SELF_REPORTED）。
"""

import json
from datetime import datetime, timezone
from pathlib import Path


PATCH_CONTRACT_PATH = Path(__file__).resolve().parent / "patch_contract.json"
PATCH_EVIDENCE_SCHEMA = "PATCH-EVIDENCE-2"

PATCH_CONTRACT_FIELDS = (
    "change_id", "implementation_contract_hash", "allowed_files",
    "allowed_functions", "forbidden_files", "forbidden_modules",
    "expected_authority_delta", "expected_active_feature_delta",
    "schema_change_allowed", "expected_golden_change",
)

# Actual/Evidence 中禁止出现的关键词（属于 Contract Authority）
FORBIDDEN_ACTUAL_KEYS = ("expected", "allowed", "approved")

FORBIDDEN_IMPORT_PREFIXES = ("research.", "ablation.", "future_label.",
                             "legacy.")


def patch_contract_template() -> dict:
    return {
        "schema": "PATCH-CONTRACT-2",
        "change_id": "",
        "implementation_contract_hash": "",
        "allowed_files": [],
        "allowed_functions": [],
        "forbidden_files": [],
        "forbidden_modules": [],
        "expected_authority_delta": [],
        "expected_active_feature_delta": [],
        "schema_change_allowed": False,
        "expected_golden_change": {"max_count": 0, "allowed_fields": []},
    }


def load_patch_contract(path=None) -> dict:
    path = Path(path) if path else PATCH_CONTRACT_PATH
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def validate_patch_contract(contract: dict) -> dict:
    errors = [f for f in PATCH_CONTRACT_FIELDS
              if contract.get(f) is None]
    golden = contract.get("expected_golden_change") or {}
    if golden.get("max_count") is None:
        errors.append("expected_golden_change.max_count")
    return {"change_id": contract.get("change_id"),
            "valid": not errors, "missing": errors}


def validate_patch_evidence(evidence) -> dict:
    """PATCH-EVIDENCE-2 契约校验（SF-2）。"""
    if evidence is None:
        return {"status": "PATCH_NOT_PROVEN",
                "reason": "patch_evidence 缺失：No Actual Evidence ≠ "
                          "No Change"}
    if not isinstance(evidence, dict):
        return {"status": "PATCH_NOT_PROVEN", "reason": "evidence 非法"}
    if evidence.get("schema") != PATCH_EVIDENCE_SCHEMA:
        return {"status": "PATCH_NOT_PROVEN",
                "reason": f"schema != {PATCH_EVIDENCE_SCHEMA}"}
    if not evidence.get("diff_hash"):
        return {"status": "PATCH_NOT_PROVEN", "reason": "diff_hash 缺失"}
    if not isinstance(evidence.get("changed_files"), list):
        return {"status": "PATCH_NOT_PROVEN",
                "reason": "changed_files 缺失或非法"}
    return {"status": "PATCH_READY", "reason": "patch evidence 有效"}


def _self_declared_expected(evidence: dict) -> list:
    """Evidence（含嵌套 key）中出现 Contract Authority 词汇 → 无效。"""
    found = []
    stack = [evidence]
    while stack:
        node = stack.pop()
        if not isinstance(node, dict):
            continue
        for key, value in node.items():
            low = str(key).lower()
            if any(w in low for w in FORBIDDEN_ACTUAL_KEYS):
                found.append(key)
            if isinstance(value, (dict, list)):
                stack.extend(value if isinstance(value, list)
                             else [value])
    return sorted(set(found))


def _function_scope_check(contract: dict, changed_functions: list) -> list:
    allowed = set(contract.get("allowed_functions") or ())
    if not allowed:
        return []
    out = [f for f in changed_functions if f not in allowed]
    return [{"kind": "FUNCTION_SCOPE",
             "detail": out}] if out else []


def _forbidden_import_check(contract: dict, import_delta: list) -> list:
    forbidden_modules = [m.rstrip(".") for m in
                         (contract.get("forbidden_modules") or [])]
    violations = []
    for imp in import_delta or []:
        target = imp.get("target") if isinstance(imp, dict) else str(imp)
        if any(target == m or target.startswith(m + ".")
               for m in forbidden_modules):
            violations.append(target)
        if any(target.startswith(p) for p in FORBIDDEN_IMPORT_PREFIXES):
            violations.append(target)
    return [{"kind": "FORBIDDEN_DEPENDENCY",
             "detail": violations}] if violations else []


def _authority_delta_from_graphs(before: dict, after: dict) -> dict:
    """从 Authority Graph 计算独立 authority / writer / root delta。"""
    def _auth_index(graph: dict) -> dict:
        return {m: n.get("authority") for m, n in
                (graph.get("nodes") or {}).items()
                if n.get("authority") not in (None, "NONE")}

    def _writers(graph: dict) -> dict:
        out = {}
        for m, n in (graph.get("nodes") or {}).items():
            w = n.get("field_writers") or n.get("writes") or []
            if w:
                out[m] = w
        return out

    b_auth, a_auth = _auth_index(before), _auth_index(after)
    new_authorities = sorted(set(a_auth) - set(b_auth))
    writer_delta = {}
    b_w, a_w = _writers(before), _writers(after)
    for m in a_w:
        if b_w.get(m) != a_w[m]:
            writer_delta[m] = a_w[m]
    roots_b = set((before.get("roots") or {}).values())
    roots_a = set((after.get("roots") or {}).values())
    root_delta = sorted(roots_a - roots_b)
    return {"new_authorities": new_authorities,
            "writer_delta": writer_delta,
            "production_root_delta": root_delta}


def _feature_delta_from_manifests(before: dict, after: dict) -> dict:
    """Feature Diff = manifest-derived（SF-2）。"""
    def _active(manifest: dict) -> set:
        return {f for f, info in (manifest or {}).items()
                if info.get("state") == "ACTIVE"}
    b, a = _active(before), _active(after)
    return {"newly_active": sorted(a - b),
            "retired": sorted(b - a)}


def _schema_changed_from_hashes(evidence: dict) -> bool | None:
    """Schema Diff = hash-derived：before_hash != after_hash。"""
    delta = evidence.get("schema_delta") or {}
    before = delta.get("hash_before")
    after = delta.get("hash_after")
    if before is None or after is None:
        return None
    return before != after


def audit_patch_scope(contract: dict, patch_evidence: dict,
                      authority_graph_before: dict,
                      authority_graph_after: dict,
                      feature_manifest_before: dict = None,
                      feature_manifest_after: dict = None) -> dict:
    """Diff Scope Audit（SF-2 独立验证，Production 禁止 SELF_REPORTED）。

    Production Mode 要求全部独立证据齐备，缺任一 → PATCH_NOT_PROVEN：
        patch_evidence（PATCH-EVIDENCE-2）
        authority_graph_before / after
        feature_manifest_after（before 默认 Frozen Production Manifest）
    """
    validation = validate_patch_contract(contract)
    if not validation["valid"]:
        return {"change_id": contract.get("change_id"),
                "verdict": "PATCH_REJECTED",
                "reason": f"Patch Contract 无效，缺失："
                          f"{validation['missing']}"}
    evidence_check = validate_patch_evidence(patch_evidence)
    missing_evidence = []
    if evidence_check["status"] != "PATCH_READY":
        missing_evidence.append("patch_evidence")
    if authority_graph_before is None:
        missing_evidence.append("authority_graph_before")
    if authority_graph_after is None:
        missing_evidence.append("authority_graph_after")
    if feature_manifest_after is None:
        missing_evidence.append("feature_manifest_after")
    if missing_evidence:
        return {"schema": "SCOPE-2",
                "change_id": contract.get("change_id"),
                "verdict": "PATCH_NOT_PROVEN",
                "reason": f"独立证据缺失：{missing_evidence}；"
                          f"No Actual Evidence ≠ No Change",
                "missing_evidence": missing_evidence,
                "rule": "Production Scope Audit 禁止 SELF_REPORTED；"
                        "Diff/Graph/Manifest 必须全部独立提供"}
    evidence = patch_evidence or {}
    violations = []
    self_declared = _self_declared_expected(evidence)
    if self_declared:
        violations.append({"kind": "SELF_DECLARED_EXPECTED",
                           "detail": self_declared})
    # File scope
    changed = set(evidence.get("changed_files") or ())
    allowed = set(contract.get("allowed_files") or ())
    forbidden = set(contract.get("forbidden_files") or ())
    out_of_scope = sorted(
        f for f in changed
        if not any(f == a or f.startswith(a.rstrip("/") + "/")
                   for a in allowed))
    forbidden_touched = sorted(
        f for f in changed
        if f in forbidden
        or any(f.startswith(x.rstrip("/") + "/") for x in forbidden))
    if out_of_scope:
        violations.append({"kind": "FILE_SCOPE", "detail": out_of_scope})
    if forbidden_touched:
        violations.append({"kind": "PROTECTED_SURFACE",
                           "detail": forbidden_touched})
    # Function scope
    violations.extend(_function_scope_check(
        contract, evidence.get("changed_functions") or []))
    # Forbidden import
    violations.extend(_forbidden_import_check(
        contract, evidence.get("import_delta") or []))
    # Authority delta（graph-derived）
    graph_authority = _authority_delta_from_graphs(
        authority_graph_before, authority_graph_after)
    expected_authority = list(contract.get("expected_authority_delta") or ())
    unexpected_authority = sorted(
        set(graph_authority["new_authorities"]) - set(expected_authority))
    if unexpected_authority:
        violations.append({"kind": "AUTHORITY_SCOPE",
                           "detail": unexpected_authority})
    if graph_authority["writer_delta"]:
        violations.append({"kind": "AUTHORITY_WRITER_DELTA",
                           "detail": graph_authority["writer_delta"]})
    if graph_authority["production_root_delta"]:
        violations.append({"kind": "PRODUCTION_ROOT_DELTA",
                           "detail":
                               graph_authority["production_root_delta"]})
    # Feature delta（manifest-derived）
    if feature_manifest_before is None:
        from QCFP_MTF.governance.minimal_trusted_release import \
            FROZEN_PRODUCTION_MANIFEST
        feature_manifest_before = FROZEN_PRODUCTION_MANIFEST
    feature_delta = _feature_delta_from_manifests(
        feature_manifest_before, feature_manifest_after)
    expected_active = list(contract.get("expected_active_feature_delta")
                           or ())
    unexpected_active = sorted(
        set(feature_delta["newly_active"]) - set(expected_active))
    if unexpected_active:
        violations.append({"kind": "FEATURE_SCOPE",
                           "detail": unexpected_active})
    # Schema delta（hash-derived）
    schema_changed = _schema_changed_from_hashes(evidence)
    if schema_changed is None:
        violations.append({"kind": "SCHEMA_EVIDENCE_MISSING",
                           "detail": "schema_delta.hash_before/after 缺失"})
    elif schema_changed and not contract.get("schema_change_allowed"):
        violations.append({"kind": "SCHEMA_SCOPE",
                           "detail": "schema 哈希变化未在 Contract 声明"})
    # Golden delta（comparator-derived）
    golden_delta = evidence.get("golden_delta") or {}
    golden_count = int(golden_delta.get("changed_count") or 0)
    golden_expected = contract.get("expected_golden_change") or {}
    max_count = int(golden_expected.get("max_count") or 0)
    if golden_count > max_count:
        violations.append({"kind": "GOLDEN_SCOPE",
                           "detail": {"golden_changed_count": golden_count,
                                      "max_count": max_count}})
    allowed_golden_fields = set(golden_expected.get("allowed_fields") or ())
    if allowed_golden_fields:
        changed_fields = set(golden_delta.get("changed_fields") or ())
        if not changed_fields.issubset(allowed_golden_fields):
            violations.append({"kind": "GOLDEN_FIELD_SCOPE",
                               "detail": sorted(
                                   changed_fields - allowed_golden_fields)})
    return {
        "schema": "SCOPE-2",
        "change_id": contract.get("change_id"),
        "scope_diff": len(out_of_scope),
        "authority_delta": sorted(graph_authority["new_authorities"]),
        "authority_source": "AUTHORITY_GRAPH",
        "active_feature_delta": feature_delta["newly_active"],
        "schema_delta": schema_changed,
        "golden_behavior_delta": golden_count,
        "violations": violations,
        "verdict": "PATCH_ACCEPTED" if not violations
        else "PATCH_REJECTED",
        "rule": "Evidence 只能报告 Observed Facts；Expected 只能来自 "
                "Frozen Contract；Diff/Graph/Manifest 必须独立提供；"
                "Self Report Authority = 0",
    }


def scope_audit_artifact(contract: dict, patch_evidence: dict, out_dir,
                         authority_graph_before: dict = None,
                         authority_graph_after: dict = None,
                         feature_manifest_after: dict = None) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    audit = audit_patch_scope(
        contract, patch_evidence, authority_graph_before,
        authority_graph_after, feature_manifest_after=feature_manifest_after)
    audit["generated_at"] = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    (out_dir / "scope_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2),
        encoding="utf-8")
    return audit
