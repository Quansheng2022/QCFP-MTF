# coding: utf-8
"""Pure Release Judge（流程治理 Sprint D #9 + FGC-1 C5/C7）

Evidence Generator 与 Pure Release Judge 完全分开：

    Evidence Generator（可以）：run tests / build graph / run replay /
        run OOS / run failure injection / calculate complexity / generate
        artifacts —— 但不能决定 Release。
    Pure Release Judge（只能）：READ / COMPARE / ISSUE VERDICT。
        禁止 run / repair / infer / default / rewrite / 测量。

C5 重构：删除 generic status-string 解释器，改为 Artifact-specific
Evaluator Registry —— 每个 evaluator 使用 Exact Enum + Exact Schema，
返回三值 PASS / FAIL / NOT_PROVEN。未知 schema / 缺失字段 / 意外枚举
一律 NOT_PROVEN，绝不猜测。

C7 收口：STANDARD 必须包含 Change Impact / Contract Result / Acceptance
Result / Review Report / Review Resolution；Bundle 必须先验证
evidence_manifest.json（哈希 + schema + identity cross-binding）。

Verdict 三态：SOFTWARE_QUALIFIED / NOT_PROVEN / REJECTED
Missing Evidence != PASS（QCFP-SPEC-RLS-001/003）。
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


BASE_ARTIFACTS = (
    "baseline.json", "spec_conformance.json",
    "architecture_conformance.json",
    "change_impact.json", "implementation_contract_result.json",
    "acceptance_result.json",
    "traceability.json", "scope_audit.json", "authority_graph.json",
    "review_report.json", "review_resolution.json",
    "golden_result.json", "invariant_result.json", "replay_result.json",
    "pit_result.json", "failure_injection_result.json",
    "complexity_diff.json", "test_summary.json",
)

HIGH_ARTIFACTS = (
    "oos_result.json", "ablation_result.json", "stress_result.json",
    "shadow_result.json",
)

PASS, FAIL, NOT_PROVEN = "PASS", "FAIL", "NOT_PROVEN"


def required_artifacts(change_tier: str = "STANDARD") -> tuple:
    base = list(BASE_ARTIFACTS)
    if change_tier == "HIGH":
        base.extend(HIGH_ARTIFACTS)
    return tuple(base)


# ---------------------------------------------------------------------------
# Artifact-specific evaluators（Exact Schema + Exact Enum，禁止 substring 猜测）
# ---------------------------------------------------------------------------

def _schema_of(data, expected: str) -> str:
    if not isinstance(data, dict):
        return NOT_PROVEN
    return PASS if data.get("schema") == expected else NOT_PROVEN


def _require(data, fields):
    missing = [f for f in fields if data.get(f) is None]
    return [] if not missing else missing


def _enum_check(data: dict, field: str, pass_values, fail_values,
                label: str) -> dict:
    """Exact Enum 三值判定：合法 PASS / 合法 FAIL / 未知 → NOT_PROVEN。"""
    value = data.get(field)
    if value in pass_values:
        return {"result": PASS, "reason": f"{label}={value}"}
    if value in fail_values:
        return {"result": FAIL, "reason": f"{label}={value}"}
    return {"result": NOT_PROVEN,
            "reason": f"{label}={value!r} 非合法枚举（不猜测）"}


def evaluate_baseline(data) -> dict:
    if _schema_of(data, "BASELINE-GATE-2") != PASS:
        return {"result": NOT_PROVEN,
                "reason": "baseline.json schema != BASELINE-GATE-2"}
    verdict = _enum_check(data, "verdict", ("BASELINE_PASS",),
                          ("BASELINE_CHANGED", "NO_BASELINE"), "verdict")
    if verdict["result"] != PASS:
        return verdict
    if data.get("pass") is not True:
        return {"result": NOT_PROVEN, "reason": "pass 字段缺失"}
    return {"result": PASS, "reason": "baseline PASS"}


def evaluate_spec(data) -> dict:
    if _schema_of(data, "SPEC-CONFORMANCE-2") != PASS:
        return {"result": NOT_PROVEN,
                "reason": "spec_conformance.json schema != SPEC-CONFORMANCE-2"}
    verdict = _enum_check(data, "verdict", ("SPEC_CONFORMANT",),
                          ("SPEC_NON_CONFORMANT",), "verdict")
    if verdict["result"] != PASS:
        return verdict
    if data.get("conformant") is not True:
        return {"result": NOT_PROVEN, "reason": "conformant 字段缺失"}
    return {"result": PASS, "reason": "spec CONFORMANT"}


def evaluate_architecture(data) -> dict:
    if _schema_of(data, "ARCHITECTURE-CONFORMANCE-2") != PASS:
        return {"result": NOT_PROVEN,
                "reason": "schema != ARCHITECTURE-CONFORMANCE-2"}
    verdict = _enum_check(data, "verdict",
                          ("ARCHITECTURE_PASS", "CONFORMANT"),
                          ("ARCHITECTURE_FAIL", "NON_CONFORMANT"), "verdict")
    if verdict["result"] != PASS:
        return verdict
    if data.get("pass") is not True:
        return {"result": NOT_PROVEN, "reason": "pass 字段缺失"}
    return {"result": PASS, "reason": "architecture PASS"}


def evaluate_change_impact(data) -> dict:
    if _schema_of(data, "CHANGE-IMPACT-2") != PASS:
        return {"result": NOT_PROVEN,
                "reason": "schema != CHANGE-IMPACT-2"}
    if data.get("approved_for_contract") is not True:
        return {"result": FAIL,
                "reason": "approved_for_contract != true"}
    tier = _enum_check(data, "tier", ("LOW", "STANDARD", "HIGH"), (),
                       "tier")
    if tier["result"] == NOT_PROVEN:
        return tier
    if not data.get("change_id") or not data.get("change_hash"):
        return {"result": NOT_PROVEN,
                "reason": "change_id/change_hash 缺失"}
    return {"result": PASS, "reason": f"change impact {data.get('tier')}"}


def evaluate_contract_result(data) -> dict:
    if _schema_of(data, "CONTRACT-RESULT-2") != PASS:
        return {"result": NOT_PROVEN,
                "reason": "schema != CONTRACT-RESULT-2"}
    verdict = _enum_check(data, "verdict", ("CONTRACT_OK",),
                          ("SCOPE_VIOLATION", "CONTRACT_INVALID"), "verdict")
    if verdict["result"] != PASS:
        return verdict
    if data.get("pass") is not True:
        return {"result": NOT_PROVEN, "reason": "pass 字段缺失"}
    return {"result": PASS, "reason": "contract OK"}


def evaluate_acceptance(data) -> dict:
    if _schema_of(data, "ACCEPTANCE-RESULT-2") != PASS:
        return {"result": NOT_PROVEN,
                "reason": "schema != ACCEPTANCE-RESULT-2"}
    verdict = _enum_check(
        data, "verdict",
        ("ACCEPTANCE_PASS",),
        ("ACCEPTANCE_FAIL", "ACCEPTANCE_CONTRACT_INVALID",
         "ORACLE_CHANGE_REJECTED"),
        "verdict")
    if verdict["result"] != PASS:
        return verdict
    if data.get("pass") is not True:
        return {"result": NOT_PROVEN, "reason": "pass 字段缺失"}
    return {"result": PASS, "reason": "acceptance PASS"}


def evaluate_traceability(data) -> dict:
    if _schema_of(data, "TRACEABILITY-2") != PASS:
        return {"result": NOT_PROVEN,
                "reason": "schema != TRACEABILITY-2"}
    verdict = _enum_check(data, "verdict", ("TRACEABILITY_PASS",),
                          ("TRACEABILITY_FAIL",), "verdict")
    if verdict["result"] != PASS:
        return verdict
    if data.get("test_index_status") != "VALID":
        return {"result": NOT_PROVEN,
                "reason": "test_index_status != VALID"}
    if data.get("active_orphan_capabilities"):
        return {"result": FAIL,
                "reason": f"active orphans="
                          f"{data.get('active_orphan_capabilities')}"}
    if data.get("pass") is not True:
        return {"result": NOT_PROVEN, "reason": "pass 字段缺失"}
    return {"result": PASS, "reason": "traceability PASS"}


def evaluate_scope(data) -> dict:
    if _schema_of(data, "SCOPE-2") != PASS:
        return {"result": NOT_PROVEN, "reason": "schema != SCOPE-2"}
    if data.get("violations"):
        return {"result": FAIL,
                "reason": f"violations={data.get('violations')}"}
    verdict = _enum_check(data, "verdict", ("PATCH_ACCEPTED",),
                          ("PATCH_REJECTED",), "verdict")
    if verdict["result"] != PASS:
        return verdict
    return {"result": PASS, "reason": "scope accepted"}


def evaluate_authority_graph(data) -> dict:
    if _schema_of(data, "AUTHORITY-GRAPH-2") != PASS:
        return {"result": NOT_PROVEN,
                "reason": "schema != AUTHORITY-GRAPH-2"}
    verdict = _enum_check(
        data, "verdict", ("AUTHORITY_OK",),
        ("AUTHORITY_DUPLICATE", "AUTHORITY_UNAUTHORIZED_WRITER"), "verdict")
    if verdict["result"] != PASS:
        return verdict
    if data.get("duplicate_authorities"):
        return {"result": FAIL,
                "reason": "duplicate authorities present"}
    if data.get("unauthorized_writers"):
        return {"result": FAIL,
                "reason": "unauthorized writers present"}
    return {"result": PASS, "reason": "authority OK"}


def evaluate_review_report(data) -> dict:
    if _schema_of(data, "REVIEW-2") != PASS:
        return {"result": NOT_PROVEN, "reason": "schema != REVIEW-2"}
    if data.get("certification_authority") not in (None, "None"):
        return {"result": FAIL,
                "reason": "reviewer 不得持有 certification authority"}
    return {"result": PASS, "reason": "review report present"}


def evaluate_review_resolution(data) -> dict:
    if _schema_of(data, "REVIEW-RESOLUTION-2") != PASS:
        return {"result": NOT_PROVEN,
                "reason": "schema != REVIEW-RESOLUTION-2"}
    if int(data.get("open_critical") or 0) > 0:
        return {"result": FAIL, "reason": "open critical findings"}
    if int(data.get("open_major") or 0) > 0:
        return {"result": FAIL, "reason": "open major findings"}
    gate = data.get("gate") or {}
    if gate.get("verdict") == "REJECTED":
        return {"result": FAIL, "reason": "review gate REJECTED"}
    return {"result": PASS, "reason": "review resolved"}


def evaluate_golden(data) -> dict:
    if _schema_of(data, "GOLDEN-2") != PASS:
        return {"result": NOT_PROVEN, "reason": "schema != GOLDEN-2"}
    status = _enum_check(data, "status", ("PASS",), ("FAIL",), "status")
    if status["result"] != PASS:
        return status
    missing = [f for f in ("n_total", "n_failed", "critical_failures")
               if data.get(f) is None]
    if missing:
        return {"result": NOT_PROVEN,
                "reason": f"golden 缺失字段: {missing}"}
    if not (int(data.get("n_total")) > 0
            and int(data.get("n_failed")) == 0
            and int(data.get("critical_failures")) == 0):
        return {"result": FAIL,
                "reason": "golden counts 不满足（n_total>0, n_failed=0, "
                          "critical=0）"}
    return {"result": PASS, "reason": "golden PASS"}


def evaluate_invariant(data) -> dict:
    if _schema_of(data, "INVARIANT-2") != PASS:
        return {"result": NOT_PROVEN, "reason": "schema != INVARIANT-2"}
    status = _enum_check(data, "status", ("PASS",), ("FAIL",), "status")
    if status["result"] != PASS:
        return status
    if data.get("failures"):
        return {"result": FAIL,
                "reason": f"failures={data.get('failures')}"}
    return {"result": PASS, "reason": "invariant PASS"}


def evaluate_replay(data) -> dict:
    if _schema_of(data, "REPLAY-2") != PASS:
        return {"result": NOT_PROVEN, "reason": "schema != REPLAY-2"}
    missing = [f for f in ("n_current_release", "eligible_rate",
                           "exact_rate", "critical_mismatch")
               if data.get(f) is None]
    if missing:
        return {"result": NOT_PROVEN,
                "reason": f"replay 缺失字段: {missing}"}
    if not (int(data.get("n_current_release")) > 0
            and float(data.get("eligible_rate")) == 1.0
            and float(data.get("exact_rate")) == 1.0
            and int(data.get("critical_mismatch")) == 0):
        return {"result": FAIL,
                "reason": "replay 条件不满足（eligible/exact=1.0, "
                          "critical_mismatch=0）"}
    return {"result": PASS, "reason": "replay deterministic"}


def evaluate_pit(data) -> dict:
    if _schema_of(data, "PIT-2") != PASS:
        return {"result": NOT_PROVEN, "reason": "schema != PIT-2"}
    status = _enum_check(data, "status", ("PASS",), ("FAIL",), "status")
    if status["result"] != PASS:
        return status
    return {"result": PASS, "reason": "pit PASS"}


def evaluate_failure_injection(data) -> dict:
    if _schema_of(data, "FAILURE-INJECTION-2") != PASS:
        return {"result": NOT_PROVEN,
                "reason": "schema != FAILURE-INJECTION-2"}
    status = _enum_check(data, "status", ("PASS",), ("FAIL",), "status")
    if status["result"] != PASS:
        return status
    if data.get("failure_escaped_count") is None:
        return {"result": NOT_PROVEN,
                "reason": "failure_escaped_count 缺失"}
    if int(data.get("failure_escaped_count")) != 0:
        return {"result": FAIL,
                "reason": "failure_escaped_count != 0"}
    return {"result": PASS, "reason": "failure injection PASS"}


def evaluate_complexity(data) -> dict:
    if _schema_of(data, "COMPLEXITY-2") != PASS:
        return {"result": NOT_PROVEN, "reason": "schema != COMPLEXITY-2"}
    verdict = _enum_check(data, "verdict",
                          ("WITHIN_BUDGET", "COMPLEXITY_OK"),
                          ("COMPLEXITY_VIOLATION",), "verdict")
    if verdict["result"] != PASS:
        return verdict
    if data.get("pass") is not True:
        return {"result": NOT_PROVEN, "reason": "pass 字段缺失"}
    return {"result": PASS, "reason": "complexity within budget"}


def evaluate_test_summary(data) -> dict:
    if _schema_of(data, "TEST-SUMMARY-2") != PASS:
        return {"result": NOT_PROVEN, "reason": "schema != TEST-SUMMARY-2"}
    status = _enum_check(data, "status", ("PASS",), ("FAIL",), "status")
    if status["result"] != PASS:
        return status
    if data.get("n_failed") is None:
        return {"result": NOT_PROVEN, "reason": "n_failed 缺失"}
    if int(data.get("n_failed")) != 0:
        return {"result": FAIL, "reason": "n_failed != 0"}
    return {"result": PASS, "reason": "test summary PASS"}


def evaluate_oos(data) -> dict:
    if _schema_of(data, "OOS-2") != PASS:
        return {"result": NOT_PROVEN, "reason": "schema != OOS-2"}
    status = _enum_check(data, "status", ("OOS_PASS",), ("OOS_FAIL",),
                         "status")
    if status["result"] != PASS:
        return status
    if data.get("comparable") is not True \
            or data.get("evidence_not_down") is not True:
        return {"result": FAIL, "reason": "oos comparable/evidence_not_down"}
    return {"result": PASS, "reason": "oos PASS"}


def evaluate_ablation(data) -> dict:
    if _schema_of(data, "ABLATION-2") != PASS:
        return {"result": NOT_PROVEN, "reason": "schema != ABLATION-2"}
    verdict = _enum_check(data, "verdict", ("INCREMENTAL_ALPHA",),
                          ("NO_INCREMENTAL_ALPHA",), "verdict")
    if verdict["result"] != PASS:
        return verdict
    if data.get("pass") is not True:
        return {"result": NOT_PROVEN, "reason": "pass 字段缺失"}
    return {"result": PASS, "reason": "ablation incremental"}


def evaluate_stress(data) -> dict:
    if _schema_of(data, "STRESS-2") != PASS:
        return {"result": NOT_PROVEN, "reason": "schema != STRESS-2"}
    if data.get("survivable") is not True:
        return {"result": FAIL, "reason": "survivable != true"}
    return {"result": PASS, "reason": "stress survivable"}


def evaluate_shadow(data) -> dict:
    if _schema_of(data, "SHADOW-2") != PASS:
        return {"result": NOT_PROVEN, "reason": "schema != SHADOW-2"}
    status = _enum_check(data, "status", ("PASS", "SHADOW_OK"),
                         ("FAIL", "SHADOW_DIVERGED"), "status")
    if status["result"] != PASS:
        return status
    if data.get("divergence_ok") is False:
        return {"result": FAIL, "reason": "shadow divergence not ok"}
    return {"result": PASS, "reason": "shadow PASS"}


EVALUATORS = {
    "baseline.json": evaluate_baseline,
    "spec_conformance.json": evaluate_spec,
    "architecture_conformance.json": evaluate_architecture,
    "change_impact.json": evaluate_change_impact,
    "implementation_contract_result.json": evaluate_contract_result,
    "acceptance_result.json": evaluate_acceptance,
    "traceability.json": evaluate_traceability,
    "scope_audit.json": evaluate_scope,
    "authority_graph.json": evaluate_authority_graph,
    "review_report.json": evaluate_review_report,
    "review_resolution.json": evaluate_review_resolution,
    "golden_result.json": evaluate_golden,
    "invariant_result.json": evaluate_invariant,
    "replay_result.json": evaluate_replay,
    "pit_result.json": evaluate_pit,
    "failure_injection_result.json": evaluate_failure_injection,
    "complexity_diff.json": evaluate_complexity,
    "test_summary.json": evaluate_test_summary,
    "oos_result.json": evaluate_oos,
    "ablation_result.json": evaluate_ablation,
    "stress_result.json": evaluate_stress,
    "shadow_result.json": evaluate_shadow,
}


# ---------------------------------------------------------------------------
# Evidence Integrity（C5/C7）
# ---------------------------------------------------------------------------

IDENTITY_FIELDS = ("change_id", "baseline_id", "release_id")


def _canonical_json(data) -> str:
    return json.dumps(data, sort_keys=True, ensure_ascii=False,
                      default=str)


def _bundle_hash(change_id, release_id, baseline_id, artifacts) -> str:
    """Bundle Hash：artifact name ASC canonical 列表（SF-3）。"""
    canonical = json.dumps(
        {"change_id": change_id, "release_id": release_id,
         "baseline_id": baseline_id,
         "artifacts": sorted(artifacts, key=lambda a: a["name"])},
        sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def make_evidence_manifest(bundle: dict, change_id, release_id,
                           baseline_id) -> dict:
    """纯函数：从 in-memory bundle 生成 manifest（不改 artifact、不写文件）。"""
    artifacts = []
    for name in sorted(bundle):
        data = bundle[name]
        if not isinstance(data, dict):
            return {"pack_status": "PACK_NOT_PROVEN",
                    "reason": f"{name} 非 dict artifact", "manifest": None}
        if not data.get("schema"):
            return {"pack_status": "PACK_NOT_PROVEN",
                    "reason": f"{name} schema 缺失（不允许自动填）",
                    "manifest": None}
        artifacts.append({
            "name": name,
            "schema": data["schema"],
            "sha256": hashlib.sha256(
                _canonical_json(data).encode("utf-8")).hexdigest(),
            "change_id": data.get("change_id", ""),
            "release_id": data.get("release_id", ""),
            "baseline_id": data.get("baseline_id", ""),
        })
    manifest = {
        "bundle_schema": "EVIDENCE-BUNDLE-2",
        "change_id": change_id,
        "release_id": release_id,
        "baseline_id": baseline_id,
        "artifacts": artifacts,
        "bundle_hash": _bundle_hash(change_id, release_id, baseline_id,
                                    artifacts),
    }
    return {"pack_status": "PACK_ACCEPTED", "manifest": manifest,
            "reason": ""}


def validate_pack_identity(bundle: dict, change_id, release_id,
                           baseline_id) -> dict:
    """SF-3：Pack 请求 identity 是期望值，不是改写目标。
    mismatch → PACK_REJECTED；missing → PACK_NOT_PROVEN。"""
    expected = {"change_id": change_id, "release_id": release_id,
                "baseline_id": baseline_id}
    rejected, not_proven = [], []
    for name, data in bundle.items():
        if not isinstance(data, dict):
            not_proven.append(f"{name}(非 dict)")
            continue
        missing = [f for f in IDENTITY_FIELDS if not data.get(f)]
        if missing:
            not_proven.append(f"{name}(missing {missing})")
            continue
        mism = [f for f in IDENTITY_FIELDS if data.get(f) != expected[f]]
        if mism:
            rejected.append({"artifact": name, "mismatch": mism})
    if rejected:
        return {"status": "PACK_REJECTED", "rejected": rejected}
    if not_proven:
        return {"status": "PACK_NOT_PROVEN", "missing_identity": not_proven}
    return {"status": "PACK_OK"}


def build_evidence_manifest(bundle_dir, change_id, release_id,
                            baseline_id, out_dir) -> dict:
    """SF-3 Read-Only Evidence Pack：READ / VERIFY / HASH / INDEX。

    明确禁止 MODIFY / REPAIR / NORMALIZE IDENTITY / INVENT IDENTITY。
    输入 artifact 的 SHA256 在运行前后必须完全不变。"""
    bundle_dir = Path(bundle_dir)
    out_dir = Path(out_dir)
    if not bundle_dir.exists():
        return {"pack_status": "PACK_NOT_PROVEN",
                "reason": "bundle 目录不存在", "manifest": None}
    bundle = {}
    for p in sorted(bundle_dir.glob("*.json")):
        if p.name == "evidence_manifest.json":
            continue
        bundle[p.name] = json.loads(p.read_text(encoding="utf-8"))
    identity_check = validate_pack_identity(
        bundle, change_id, release_id, baseline_id)
    if identity_check["status"] != "PACK_OK":
        result = {"pack_status": identity_check["status"], "manifest": None}
        result.update({k: v for k, v in identity_check.items()
                       if k != "status"})
        return result
    result = make_evidence_manifest(bundle, change_id, release_id,
                                    baseline_id)
    if result["pack_status"] != "PACK_ACCEPTED":
        return result
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "evidence_manifest.json").write_text(
        json.dumps(result["manifest"], ensure_ascii=False, indent=2),
        encoding="utf-8")
    return result


def verify_evidence_manifest(bundle: dict, manifest: dict,
                             required=None) -> dict:
    """Judge 验证 Manifest：bundle_hash + 必需 artifact 全列出 +
    hash 一致 + schema 一致（SF-4 固定顺序第 3/4/5 步）。"""
    if not isinstance(manifest, dict) \
            or manifest.get("bundle_schema") != "EVIDENCE-BUNDLE-2":
        return {"valid": False,
                "problems": ["schema != EVIDENCE-BUNDLE-2"]}
    recomputed = _bundle_hash(
        manifest.get("change_id"), manifest.get("release_id"),
        manifest.get("baseline_id"), manifest.get("artifacts") or [])
    problems = []
    if recomputed != manifest.get("bundle_hash"):
        problems.append("bundle_hash 不匹配")
    listed = {a.get("name"): a for a in manifest.get("artifacts") or []}
    for req in (required or []):
        if req not in listed:
            problems.append(f"manifest 缺少必需 artifact: {req}")
    for name, data in bundle.items():
        entry = listed.get(name)
        if entry is None:
            problems.append(f"{name} 不在 manifest")
            continue
        sha = hashlib.sha256(
            _canonical_json(data).encode("utf-8")).hexdigest()
        if entry.get("sha256") != sha:
            problems.append(f"{name} hash 不匹配")
        if entry.get("schema") != data.get("schema"):
            problems.append(f"{name} schema 不匹配")
    return {"valid": not problems, "problems": problems}


def validate_artifact_identity(artifact: dict, expected: dict) -> dict:
    """SF-4 Full Identity：3/3 present + 3/3 exact match。
    缺失 → NOT_PROVEN；不一致 → REJECTED。"""
    if not isinstance(artifact, dict):
        return {"result": NOT_PROVEN, "reason": "artifact 非 dict"}
    missing = [f for f in IDENTITY_FIELDS if not artifact.get(f)]
    if missing:
        return {"result": NOT_PROVEN,
                "reason": f"identity 缺失: {missing}"}
    mism = [f for f in IDENTITY_FIELDS
            if artifact.get(f) != expected.get(f)]
    if mism:
        return {"result": "REJECTED",
                "reason": f"identity 不一致: {mism}"}
    return {"result": PASS, "reason": "identity 3/3 匹配"}


# ---------------------------------------------------------------------------
# Pure Judge
# ---------------------------------------------------------------------------

def issue_release_verdict(evidence_bundle: dict,
                          change_tier: str = None,
                          evidence_manifest: dict = None) -> dict:
    """READ → COMPARE → ISSUE VERDICT。

    SF-4 固定验证顺序（不允许乱序）：
        1. Manifest exists?
        2. Manifest schema valid?
        3. bundle_hash valid?
        4. Required artifact set complete?
        5. Individual artifact hash valid?
        6. Full identity valid?（expected identity 来自 Manifest）
        7. Artifact schema valid?
        8. Artifact-specific evaluator
        9. Aggregate verdict

    * change_tier 缺省时从 bundle 的 change_impact.json 读取
      （Judge 无权接受调用方手动降级）；
    * 任何 FAIL → REJECTED；无 FAIL 但 ≥1 NOT_PROVEN → NOT_PROVEN；
      全部 PASS → SOFTWARE_QUALIFIED。
    """
    if not isinstance(evidence_bundle, dict):
        return {"verdict": NOT_PROVEN, "reason": "bundle 非法",
                "certificate": "RELEASE-NOT-PROVEN"}
    # 1. Manifest 必须存在（SF-4：无 Manifest 不得 QUALIFIED）
    if evidence_manifest is None:
        return {"verdict": NOT_PROVEN,
                "reason": "缺少 evidence_manifest.json —— "
                          "Manifest-less Qualification 禁止（SF-4）",
                "certificate": "RELEASE-NOT-PROVEN"}
    # 2. Manifest schema
    if evidence_manifest.get("bundle_schema") != "EVIDENCE-BUNDLE-2":
        return {"verdict": NOT_PROVEN,
                "reason": "evidence_manifest schema != EVIDENCE-BUNDLE-2",
                "certificate": "RELEASE-NOT-PROVEN"}
    expected_identity = {
        "change_id": evidence_manifest.get("change_id", ""),
        "release_id": evidence_manifest.get("release_id", ""),
        "baseline_id": evidence_manifest.get("baseline_id", ""),
    }
    if not all(expected_identity.values()):
        return {"verdict": NOT_PROVEN,
                "reason": "evidence_manifest identity 不完整",
                "certificate": "RELEASE-NOT-PROVEN"}
    # 3. bundle_hash
    recomputed = _bundle_hash(
        expected_identity["change_id"], expected_identity["release_id"],
        expected_identity["baseline_id"],
        evidence_manifest.get("artifacts") or [])
    if recomputed != evidence_manifest.get("bundle_hash"):
        return {"verdict": NOT_PROVEN,
                "reason": "bundle_hash 不匹配",
                "certificate": "RELEASE-NOT-PROVEN"}
    impact = evidence_bundle.get("change_impact.json") or {}
    if change_tier is None:
        change_tier = impact.get("tier")
    if change_tier is None:
        return {"verdict": NOT_PROVEN,
                "reason": "缺少 change_impact.json 或 tier —— "
                          "Judge 不接受调用方手动指定 tier（C2）",
                "missing_artifacts": ["change_impact.json"],
                "certificate": "RELEASE-NOT-PROVEN",
                **expected_identity}
    if impact.get("tier") and change_tier != impact.get("tier"):
        return {"verdict": "REJECTED",
                "reason": f"Judge tier {change_tier} 与 change_impact tier "
                          f"{impact.get('tier')} 不一致（降级尝试）",
                "certificate": "RELEASE-REJECTED",
                **expected_identity}
    if impact.get("change_id") \
            and impact["change_id"] != expected_identity["change_id"]:
        return {"verdict": "REJECTED",
                "reason": "change_impact.change_id 与 manifest 不一致",
                "certificate": "RELEASE-REJECTED",
                **expected_identity}
    required = required_artifacts(change_tier)
    # 4. Required artifact set complete
    missing = [a for a in required if not evidence_bundle.get(a)]
    if missing:
        return {"verdict": NOT_PROVEN,
                "reason": "Missing Evidence != PASS",
                "missing_artifacts": missing,
                "certificate": "RELEASE-NOT-PROVEN",
                "change_tier": change_tier,
                **expected_identity}
    # 5. Individual artifact hash + schema（含 manifest 必需集完整性）
    manifest_check = verify_evidence_manifest(
        evidence_bundle, evidence_manifest, required=required)
    if not manifest_check["valid"]:
        return {"verdict": NOT_PROVEN,
                "reason": "evidence manifest 校验失败",
                "manifest_problems": manifest_check["problems"],
                "certificate": "RELEASE-NOT-PROVEN",
                "change_tier": change_tier,
                **expected_identity}
    # 6. Full identity（expected 来自 Manifest）
    identity_fail, identity_not_proven = [], []
    for artifact in required:
        check = validate_artifact_identity(
            evidence_bundle.get(artifact), expected_identity)
        if check["result"] == "REJECTED":
            identity_fail.append({"artifact": artifact,
                                  "reason": check["reason"]})
        elif check["result"] == NOT_PROVEN:
            identity_not_proven.append(artifact)
    if identity_fail:
        return {"verdict": "REJECTED",
                "reason": "artifact identity 与 Manifest 不一致",
                "identity_violations": identity_fail,
                "certificate": "RELEASE-REJECTED",
                "change_tier": change_tier,
                **expected_identity}
    if identity_not_proven:
        return {"verdict": NOT_PROVEN,
                "reason": "存在 identity 不完整的 artifact（3/3 缺失）",
                "missing_identity": identity_not_proven,
                "certificate": "RELEASE-NOT-PROVEN",
                "change_tier": change_tier,
                **expected_identity}
    # 7. Artifact schema valid（verify_evidence_manifest 已覆盖）
    # 8. Artifact-specific evaluator
    failed, not_proven = [], []
    evaluations = {}
    for artifact in required:
        data = evidence_bundle.get(artifact)
        evaluator = EVALUATORS.get(artifact)
        if evaluator is None:
            not_proven.append(artifact)
            evaluations[artifact] = {"result": NOT_PROVEN,
                                     "reason": "无 evaluator"}
            continue
        result = evaluator(data)
        evaluations[artifact] = result
        if result["result"] == FAIL:
            failed.append(artifact)
        elif result["result"] == NOT_PROVEN:
            not_proven.append(artifact)
    if failed:
        return {"verdict": "REJECTED",
                "reason": "存在明确违规/失败 artifact",
                "failed_artifacts": failed,
                "evaluations": evaluations,
                "certificate": "RELEASE-REJECTED",
                "change_tier": change_tier,
                **expected_identity}
    if not_proven:
        return {"verdict": NOT_PROVEN,
                "reason": "存在无法判定/证据不完整的 artifact",
                "indeterminate_artifacts": not_proven,
                "evaluations": evaluations,
                "certificate": "RELEASE-NOT-PROVEN",
                "change_tier": change_tier,
                **expected_identity}
    return {"verdict": "SOFTWARE_QUALIFIED",
            "reason": "全部必需 artifact 明确通过（含证据完整性绑定）",
            "certificate": "SOFTWARE-QUALIFIED",
            "change_tier": change_tier,
            "artifacts_checked": list(required),
            "evaluations": evaluations,
            **expected_identity,
            "rule": "QUALIFIED 只代表系统实现可信，不代表策略有效"
                    "（QCFP-SPEC-RLS-002）"}


def release_verdict_artifact(evidence_bundle: dict,
                             out_dir,
                             change_tier: str = None,
                             evidence_manifest: dict = None) -> dict:
    """写 release_verdict.json + md。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    verdict = issue_release_verdict(evidence_bundle, change_tier,
                                    evidence_manifest)
    verdict["generated_at"] = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    (out_dir / "release_verdict.json").write_text(
        json.dumps(verdict, ensure_ascii=False, indent=2),
        encoding="utf-8")
    lines = [
        "# QCFP-MTF Pure Release Judge",
        "",
        f"**Verdict：{verdict['verdict']}**",
        f"- Reason：{verdict.get('reason')}",
        f"- Certificate：{verdict.get('certificate')}",
        f"- Change Tier：{verdict.get('change_tier')}",
    ]
    for key in ("missing_artifacts", "failed_artifacts",
                "indeterminate_artifacts", "identity_violations"):
        if verdict.get(key):
            lines.append(f"- {key.replace('_', ' ').title()}："
                         f"{verdict[key]}")
    (out_dir / "release_verdict.md").write_text(
        "\n".join(lines), encoding="utf-8")
    return verdict
