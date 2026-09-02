# coding: utf-8
"""Phase 4 — Flow Governance Closure（FGC-1 + SF-1~SF-5 + Zero-Bypass）

核心原则：
    Specification defines truth.
    Runtime produces behavior.
    Tests observe behavior.
    Evidence records observations.
    Phase4 Judge aggregates evidence.
    Human freezes governance.

本模块是纯证据聚合器，不是新的 Authority（QCFP-SPEC-RLS-004）。
它只做 READ evidence → COMPARE → ISSUE verdict：
    * 不运行 pytest（回归证据由 scripts/phase4_regression_runner.py 提供）；
    * 不补齐缺失证据（缺失 → NOT_PROVEN，QCFP-SPEC-RLS-003）；
    * 不修改 evidence bundle（SF-3/SF-4 由 evidence_pack 证据证明）。

Phase 4 DoD：
    Bypass Path → SOFTWARE_QUALIFIED = 0
    Bypass Path → PRODUCTION_DSS     = 0
"""

import json
from datetime import datetime, timezone
from pathlib import Path


class EvidenceUnavailable(RuntimeError):
    """证据缺失/环境不可用 → NOT_PROVEN（不得当作 FAIL）。"""


def _root() -> Path:
    return Path(__file__).resolve().parents[3]


def _provider(gate, status, verdict, problems=None, evidence=None) -> dict:
    return {"gate": gate, "status": status, "verdict": verdict,
            "problems": list(problems or []), "evidence": dict(evidence or {})}


def _ok(gate, verdict, evidence=None) -> dict:
    return _provider(gate, "PASS", verdict, evidence=evidence)


def _fail(gate, verdict, problems, evidence=None) -> dict:
    return _provider(gate, "FAIL", verdict, problems=problems,
                     evidence=evidence)


def _not_proven(gate, verdict, problems, evidence=None) -> dict:
    return _provider(gate, "NOT_PROVEN", verdict, problems=problems,
                     evidence=evidence)


# ---------------------------------------------------------------------------
# 证据 Bundle / Schema 契约
# ---------------------------------------------------------------------------

# bundle 中每个 artifact 必须携带完整 identity（SF-4）：
#   change_id / release_id / baseline_id  3/3 present + 3/3 exact match
IDENTITY_FIELDS = ("change_id", "release_id", "baseline_id")

ARTIFACT_SCHEMAS = {
    "spec_conformance.json": "SPEC-CONFORMANCE-2",
    "baseline.json": "BASELINE-GATE-2",
    "traceability.json": "TRACEABILITY-2",
    "change_impact.json": "CHANGE-IMPACT-2",
    "implementation_contract_result.json": "CONTRACT-RESULT-2",
    "acceptance_result.json": "ACCEPTANCE-RESULT-2",
    "scope_audit.json": "SCOPE-2",
    "review_report.json": "REVIEW-2",
    "review_resolution.json": "REVIEW-RESOLUTION-2",
    "fgc_bypass_suite.json": "FGC-BYPASS-SUITE-1",
    "evidence_pack_readonly.json": "EVIDENCE-PACK-READONLY-1",
    "evidence_manifest_verification.json": "EVIDENCE-MANIFEST-VERIFY-1",
}
# 注：evidence_pack_readonly.json（EVIDENCE-PACK-READONLY-1）与
# evidence_manifest_verification.json（EVIDENCE-MANIFEST-VERIFY-1）是
# 位于 out_dir（audit/phase4/）的“派生验证证据”，不属于 evidence bundle
# 输入（避免自引用）；对应 Provider 从 out_dir 读取。

REQUIRED_REGRESSION_SUITES = (
    "phase4_flow", "bypass", "phase1", "phase3",
    "decision", "governance", "full_core",
)


def _load_bundle(bundle_dir) -> dict:
    """读取 bundle 目录全部 JSON artifact（evidence_manifest 除外）。"""
    bundle_dir = Path(bundle_dir)
    if not bundle_dir.exists():
        raise EvidenceUnavailable(f"evidence bundle 目录缺失: {bundle_dir}")
    bundle = {}
    for p in sorted(bundle_dir.glob("*.json")):
        if p.name == "evidence_manifest.json":
            continue
        bundle[p.name] = json.loads(p.read_text(encoding="utf-8"))
    return bundle


def _artifact(bundle, name, schema=None) -> dict:
    """取 artifact；缺失 → EvidenceUnavailable（NOT_PROVEN）。"""
    data = bundle.get(name)
    if data is None:
        raise EvidenceUnavailable(f"artifact 缺失: {name}")
    if schema and data.get("schema") != schema:
        raise EvidenceUnavailable(
            f"{name} schema != {schema}（不允许自动修补）")
    return data


def _bundle_identity_ok(bundle, manifest=None) -> tuple:
    """SF-4：全部 artifact 的 change_id/release_id/baseline_id
    present + 与 Manifest 期望 identity 精确一致。"""
    expected = {
        "change_id": (manifest or {}).get("change_id", ""),
        "release_id": (manifest or {}).get("release_id", ""),
        "baseline_id": (manifest or {}).get("baseline_id", ""),
    }
    missing, mismatched = [], []
    for name in sorted(bundle):
        data = bundle[name]
        miss = [f for f in IDENTITY_FIELDS if not data.get(f)]
        if miss:
            missing.append({"artifact": name, "missing": miss})
            continue
        mism = [f for f in IDENTITY_FIELDS
                if data.get(f) != expected.get(f)]
        if mism:
            mismatched.append({"artifact": name, "mismatch": mism})
    return missing, mismatched


# ---------------------------------------------------------------------------
# Phase 4 Gate Providers（只消费证据）
# ---------------------------------------------------------------------------

def spec_provider(bundle) -> dict:
    data = _artifact(bundle, "spec_conformance.json",
                     ARTIFACT_SCHEMAS["spec_conformance.json"])
    if data.get("conformant") is not True \
            or data.get("verdict") != "SPEC_CONFORMANT":
        return _fail("SPEC", "SPEC_NON_CONFORMANT",
                     problems=["spec_conformance 非 CONFORMANT"])
    return _ok("SPEC", "SPEC_CONFORMANT", evidence=data)


def baseline_provider(bundle) -> dict:
    data = _artifact(bundle, "baseline.json",
                     ARTIFACT_SCHEMAS["baseline.json"])
    if data.get("pass") is not True \
            or data.get("verdict") != "BASELINE_PASS":
        return _fail("BASELINE", "BASELINE_CHANGED",
                     problems=[f"baseline drift: "
                               f"{data.get('verdict')}"],
                     evidence=data)
    return _ok("BASELINE", "BASELINE_PASS", evidence=data)


def traceability_provider(bundle) -> dict:
    data = _artifact(bundle, "traceability.json",
                     ARTIFACT_SCHEMAS["traceability.json"])
    if data.get("pass") is not True \
            or data.get("verdict") != "TRACEABILITY_PASS":
        return _fail("TRACEABILITY", "TRACEABILITY_FAIL",
                     problems=[data.get("verdict", "PASS != true")],
                     evidence=data)
    return _ok("TRACEABILITY", "TRACEABILITY_PASS", evidence=data)


def change_process_provider(bundle) -> dict:
    """C1/C2/C3/C4 + SF-1/SF-2：Change Impact → Contract → Oracle → Patch。"""
    impact = _artifact(bundle, "change_impact.json",
                       ARTIFACT_SCHEMAS["change_impact.json"])
    contract = _artifact(
        bundle, "implementation_contract_result.json",
        ARTIFACT_SCHEMAS["implementation_contract_result.json"])
    acceptance = _artifact(bundle, "acceptance_result.json",
                           ARTIFACT_SCHEMAS["acceptance_result.json"])
    problems = []
    if impact.get("approved_for_contract") is not True:
        problems.append("change_impact 未 approved_for_contract")
    if impact.get("observed_diff_valid") is not True \
            or impact.get("observed_tier") is None:
        problems.append("change_impact 未基于 Observed Diff（SF-1）")
    if contract.get("verdict") != "CONTRACT_OK" \
            or contract.get("pass") is not True:
        problems.append("implementation contract 未通过（C4）")
    if acceptance.get("verdict") != "ACCEPTANCE_PASS" \
            or acceptance.get("pass") is not True:
        problems.append("acceptance oracle 未通过（C3）")
    if problems:
        return _fail("CHANGE_PROCESS", "CHANGE_PROCESS_FAIL",
                     problems=problems)
    return _ok("CHANGE_PROCESS", "CHANGE_PROCESS_OK",
               evidence={"impact_status": impact.get("status"),
                         "contract_verdict": contract.get("verdict"),
                         "acceptance_verdict": acceptance.get("verdict")})


def patch_scope_provider(bundle) -> dict:
    data = _artifact(bundle, "scope_audit.json",
                     ARTIFACT_SCHEMAS["scope_audit.json"])
    problems = []
    if data.get("verdict") != "PATCH_ACCEPTED":
        problems.append(f"scope audit: {data.get('verdict')}")
    if data.get("violations"):
        problems.append(f"scope violations: {data.get('violations')}")
    if data.get("authority_source") != "AUTHORITY_GRAPH":
        problems.append("authority_source != AUTHORITY_GRAPH（SF-2）")
    if problems:
        return _fail("PATCH_SCOPE", "PATCH_REJECTED",
                     problems=problems, evidence=data)
    return _ok("PATCH_SCOPE", "PATCH_ACCEPTED", evidence=data)


def _suite_counts(suite: dict) -> tuple:
    try:
        collected = int(suite.get("collected") or 0)
        passed = int(suite.get("passed") or 0)
        failed = int(suite.get("failed") or 0)
        errors = int(suite.get("errors") or 0)
        skipped = int(suite.get("skipped") or 0)
    except (TypeError, ValueError):
        return None
    return collected, passed, failed, errors, skipped


def _validate_suite(suite: dict) -> dict:
    counts = _suite_counts(suite)
    if counts is None:
        return {"valid": False,
                "problem": "suite counts 非整数或缺失"}
    collected, passed, failed, errors, skipped = counts
    if collected != passed + failed + errors + skipped:
        return {"valid": False,
                "problem": f"collected({collected}) != "
                           f"passed+failed+errors+skipped "
                           f"({passed}+{failed}+{errors}+{skipped})"}
    if suite.get("status") != "PASS":
        return {"valid": False,
                "problem": f"status={suite.get('status')} != PASS"}
    if passed <= 0:
        return {"valid": False, "problem": "PASS 但 passed <= 0"}
    if failed or errors or skipped:
        return {"valid": False,
                "problem": "PASS 但 failed/errors/skipped > 0"}
    return {"valid": True, "problem": ""}


def flow_governance_provider(regression: dict) -> dict:
    suites = regression.get("suites") or {}
    suite = suites.get("phase4_flow")
    if suite is None:
        raise EvidenceUnavailable("regression 缺 phase4_flow suite")
    check = _validate_suite(suite)
    if not check["valid"]:
        return _fail("FLOW_GOVERNANCE", "FLOW_GOVERNANCE_FAIL",
                     problems=[check["problem"]], evidence=suite)
    return _ok("FLOW_GOVERNANCE", "FLOW_GOVERNANCE_PASS", evidence=suite)


def zero_bypass_provider(regression: dict, bundle: dict) -> dict:
    """DoD：Bypass Path → QUALIFIED/DSS = 0。

    escaped 不硬编码 0：从 bypass suite 计数推导
    （PASS + failed/errors=0 ⇒ 全部攻击面被拦截 ⇒ escaped=0）。
    """
    suites = regression.get("suites") or {}
    suite = suites.get("bypass")
    if suite is None:
        raise EvidenceUnavailable("regression 缺 bypass suite")
    check = _validate_suite(suite)
    problems = []
    if not check["valid"]:
        problems.append(check["problem"])
    counts = _suite_counts(suite)
    bypass_suite = _artifact(bundle, "fgc_bypass_suite.json",
                             ARTIFACT_SCHEMAS["fgc_bypass_suite.json"])
    if bypass_suite.get("all_blocked") is not True:
        problems.append("fgc_bypass_suite.all_blocked != true")
    escaped = int(counts[2]) + int(counts[3]) if counts else -1
    if problems:
        return _fail("ZERO_BYPASS", "BYPASS_ESCAPED",
                     problems=problems,
                     evidence={"bypass_escaped": escaped,
                               "suite": suite,
                               "bypass_suite": bypass_suite})
    return _ok("ZERO_BYPASS", "ZERO_BYPASS_PASS",
               evidence={"bypass_escaped": escaped,
                         "bypass_collected": counts[0],
                         "rule": "escaped = bypass suite failed+errors "
                                 "（全部攻击面被拦截 ⇒ 0）"})


def review_resolution_provider(bundle) -> dict:
    report = _artifact(bundle, "review_report.json",
                       ARTIFACT_SCHEMAS["review_report.json"])
    resolution = _artifact(bundle, "review_resolution.json",
                           ARTIFACT_SCHEMAS["review_resolution.json"])
    problems = []
    if report.get("certification_authority") not in (None, "None"):
        problems.append("reviewer 持有 certification authority（禁止）")
    gate = resolution.get("gate") or {}
    if int(resolution.get("open_critical") or 0) > 0:
        problems.append("open CRITICAL findings > 0")
    if int(resolution.get("open_major") or 0) > 0:
        problems.append("open MAJOR findings > 0")
    if gate.get("allowed") is not True:
        problems.append(f"review gate: {gate.get('verdict')}")
    if problems:
        return _fail("REVIEW_RESOLUTION", "REVIEW_NOT_RESOLVED",
                     problems=problems)
    return _ok("REVIEW_RESOLUTION", "REVIEW_RESOLVED",
               evidence={"report_verdict": report.get("verdict"),
                         "resolution_verdict":
                             resolution.get("verdict"),
                         "open_critical":
                             int(resolution.get("open_critical") or 0),
                         "open_major":
                             int(resolution.get("open_major") or 0)})


def evidence_pack_sf3_provider(bundle, bundle_dir, out_dir) -> dict:
    readonly_path = Path(out_dir) / "evidence_pack_readonly.json"
    if not readonly_path.exists():
        raise EvidenceUnavailable("evidence_pack_readonly.json 缺失")
    readonly = json.loads(readonly_path.read_text(encoding="utf-8"))
    if readonly.get("schema") != \
            ARTIFACT_SCHEMAS["evidence_pack_readonly.json"]:
        raise EvidenceUnavailable("evidence_pack_readonly schema 非法")
    manifest_path = Path(bundle_dir) / "evidence_manifest.json"
    problems = []
    if readonly.get("all_unchanged") is not True:
        problems.append("Evidence Pack 修改了 artifact（SF-3 违反）")
    if readonly.get("pack_status") != "PACK_ACCEPTED":
        problems.append(f"pack: {readonly.get('pack_status')}")
    if not manifest_path.exists():
        raise EvidenceUnavailable("evidence_manifest.json 缺失")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("bundle_schema") != "EVIDENCE-BUNDLE-2":
        problems.append("evidence_manifest schema != EVIDENCE-BUNDLE-2")
    if problems:
        return _fail("EVIDENCE_PACK_SF3", "PACK_NOT_READONLY",
                     problems=problems, evidence=readonly)
    return _ok("EVIDENCE_PACK_SF3", "PACK_READONLY",
               evidence={"all_unchanged": True,
                         "manifest_schema": manifest.get("bundle_schema"),
                         "manifest_artifacts": len(
                             manifest.get("artifacts") or [])})


def manifest_identity_sf4_provider(bundle, out_dir) -> dict:
    verify_path = Path(out_dir) / "evidence_manifest_verification.json"
    if not verify_path.exists():
        raise EvidenceUnavailable(
            "evidence_manifest_verification.json 缺失")
    verification = json.loads(
        verify_path.read_text(encoding="utf-8"))
    if verification.get("schema") != \
            ARTIFACT_SCHEMAS["evidence_manifest_verification.json"]:
        raise EvidenceUnavailable(
            "evidence_manifest_verification schema 非法")
    problems = []
    if verification.get("valid") is not True:
        problems.append(f"manifest verification: "
                        f"{verification.get('problems')}")
    if verification.get("all_identity_ok") is not True:
        problems.append("identity 3/3 未全部精确匹配")
    if problems:
        return _fail("MANIFEST_IDENTITY", "IDENTITY_MISMATCH",
                     problems=problems, evidence=verification)
    return _ok("MANIFEST_IDENTITY", "MANIFEST_IDENTITY_OK",
               evidence={"artifacts_verified":
                         verification.get("artifact_count")})


def promotion_sf5_provider(bundle) -> dict:
    data = _artifact(bundle, "fgc_bypass_suite.json",
                     ARTIFACT_SCHEMAS["fgc_bypass_suite.json"])
    problems = []
    if data.get("all_blocked") is not True:
        problems.append("promotion bypass 未全部 BLOCKED")
    checks = data.get("checks") or {}
    for name, ok in checks.items():
        if ok is not True:
            problems.append(f"{name} 未 BLOCKED")
    if problems:
        return _fail("PROMOTION_SF5", "PROMOTION_BYPASS",
                     problems=problems, evidence=data)
    return _ok("PROMOTION_SF5", "PROMOTION_IDENTITY_HARDENED",
               evidence=data)


def regression_provider(regression: dict) -> dict:
    suites = regression.get("suites") or {}
    actual = set(suites.keys())
    required = set(REQUIRED_REGRESSION_SUITES)
    missing = sorted(required - actual)
    data = dict(regression)
    data["missing_suites"] = missing
    data["required_suites"] = list(REQUIRED_REGRESSION_SUITES)
    if missing:
        return _not_proven("REGRESSION", "REGRESSION_NOT_PROVEN",
                           problems=[f"missing required suites: {missing}"],
                           evidence=data)
    invalid = []
    for name in REQUIRED_REGRESSION_SUITES:
        check = _validate_suite(suites.get(name, {}))
        if not check["valid"]:
            invalid.append({"suite": name, "problem": check["problem"]})
    if invalid:
        return _fail("REGRESSION", "REGRESSION_FAIL",
                     problems=[f"suite 未满足: {invalid}"],
                     evidence=data)
    return _ok("REGRESSION", "REGRESSION_PASS", evidence=data)


# ---------------------------------------------------------------------------
# Phase 4 Gate 编排（FGC_GATE）
# ---------------------------------------------------------------------------

PHASE4_GATES = (
    ("SPEC", "P0", spec_provider),
    ("BASELINE", "P0", baseline_provider),
    ("TRACEABILITY", "P0", traceability_provider),
    ("CHANGE_PROCESS", "P0", change_process_provider),
    ("PATCH_SCOPE", "P0", patch_scope_provider),
    ("FLOW_GOVERNANCE", "P0", flow_governance_provider),
    ("ZERO_BYPASS", "P0", zero_bypass_provider),
    ("REVIEW_RESOLUTION", "P0", review_resolution_provider),
    ("EVIDENCE_PACK_SF3", "P0", evidence_pack_sf3_provider),
    ("MANIFEST_IDENTITY", "P0", manifest_identity_sf4_provider),
    ("PROMOTION_SF5", "P0", promotion_sf5_provider),
    ("REGRESSION", "P1", regression_provider),
)


def derive_close_record(gates: dict, missing: list) -> dict:
    """Freeze Stamp 全部由证据推导，不硬编码 0。"""
    bypass = gates.get("ZERO_BYPASS", {}).get("evidence", {})
    # -1 = ZERO_BYPASS 证据不足/未 PASS 时的占位（不得当作 0）；
    # 仅在 ZERO_BYPASS=PASS 时该数字是“0”的机器推导结果。
    escaped = int(bypass.get("bypass_escaped", -1) or 0)
    review = gates.get("REVIEW_RESOLUTION", {}).get("evidence", {})
    pack = gates.get("EVIDENCE_PACK_SF3", {}).get("evidence", {})
    return {
        "bypass_to_software_qualified": escaped,
        "bypass_to_production_dss": escaped,
        "evidence_pack_artifacts": int(
            pack.get("manifest_artifacts", 0) or 0),
        "review_verdict": review.get("report_verdict", "N/A"),
        "open_critical": int(review.get("open_critical") or 0),
        "open_major": int(review.get("open_major") or 0),
        "open_p0": sum(1 for name, pri, _fn in PHASE4_GATES
                       if pri == "P0"
                       and gates.get(name, {}).get("status") == "FAIL"),
        "open_p1": sum(1 for name, pri, _fn in PHASE4_GATES
                       if pri == "P1"
                       and gates.get(name, {}).get("status")
                       in ("FAIL", "NOT_PROVEN")),
        "missing_required_evidence": len(missing),
        "rule": "Freeze Stamp 只投影事实；Human Approval 后才 FROZEN",
    }


def _freeze_state(verdict: str) -> str:
    if verdict == "PHASE4_PASS":
        return "GOVERNANCE_FREEZE_CANDIDATE"
    if verdict == "PHASE4_FAIL":
        return "BLOCKED"
    return "NOT_PROVEN"


def phase4_acceptance(out_dir=None, bundle_dir=None,
                      gates=None) -> dict:
    """运行 Phase 4 全部 Gate 并产出 acceptance pack（json + md）。"""
    out_dir = Path(out_dir) if out_dir \
        else _root() / "audit" / "phase4"
    bundle_dir = Path(bundle_dir) if bundle_dir \
        else out_dir / "bundle"
    out_dir.mkdir(parents=True, exist_ok=True)
    regression_path = out_dir / "phase4_regression_summary.json"
    if not regression_path.exists():
        raise EvidenceUnavailable(
            f"regression 证据缺失（先运行 phase4_regression_runner）: "
            f"{regression_path}")
    regression = json.loads(
        regression_path.read_text(encoding="utf-8"))
    bundle = _load_bundle(bundle_dir)
    providers = gates or PHASE4_GATES
    results = {}
    for name, priority, fn in providers:
        try:
            if name in ("FLOW_GOVERNANCE", "REGRESSION"):
                result = fn(regression)
            elif name == "ZERO_BYPASS":
                result = fn(regression, bundle)
            elif name == "EVIDENCE_PACK_SF3":
                result = fn(bundle, bundle_dir, out_dir)
            elif name == "MANIFEST_IDENTITY":
                result = fn(bundle, out_dir)
            else:
                result = fn(bundle)
        except EvidenceUnavailable as exc:
            result = _not_proven(name, "EVIDENCE_UNAVAILABLE",
                                 problems=[str(exc)])
        except Exception as exc:      # 不吞异常：记录为 FAIL 供审计
            result = _fail(name, "PROVIDER_ERROR",
                           problems=[f"{type(exc).__name__}: {exc}"])
        result["priority"] = priority
        results[name] = result
    failures = [k for k, v in results.items()
                if v.get("status") == "FAIL"]
    missing = [k for k, v in results.items()
               if v.get("status") == "NOT_PROVEN"]
    if failures:
        verdict = "PHASE4_FAIL"
    elif missing:
        verdict = "PHASE4_NOT_PROVEN"
    else:
        verdict = "PHASE4_PASS"
    close_record = derive_close_record(results, missing)
    acceptance = {
        "schema": "PHASE4-ACCEPTANCE-1",
        "generated_at_utc": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "gates": results,
        "failures": failures,
        "missing_evidence": missing,
        "close_record": close_record,
        "freeze_state": _freeze_state(verdict),
        "pass": not failures and not missing,
        "verdict": verdict,
    }
    (out_dir / "phase4_acceptance.json").write_text(
        json.dumps(acceptance, ensure_ascii=False, indent=2),
        encoding="utf-8")
    lines = [
        "QCFP-MTF PHASE 4 GOVERNANCE CLOSURE RECORD",
        "================================================",
        "",
        f"Verdict      : {verdict}",
        f"Freeze State : {_freeze_state(verdict)}",
        "",
        f"Bypass to SOFTWARE_QUALIFIED : "
        f"{close_record['bypass_to_software_qualified']}",
        f"Bypass to PRODUCTION_DSS     : "
        f"{close_record['bypass_to_production_dss']}",
        f"Evidence Pack Artifacts      : "
        f"{close_record['evidence_pack_artifacts']}",
        f"Open P0                      : {close_record['open_p0']}",
        f"Open P1                      : {close_record['open_p1']}",
        f"Missing Evidence             : "
        f"{close_record['missing_required_evidence']}",
        "",
        "Gate 明细：",
    ]
    for name, gate in results.items():
        lines.append(f"- {name} [{gate.get('priority')}]: "
                     f"{gate.get('status')} / {gate.get('verdict')}")
    (out_dir / "phase4_freeze_record.txt").write_text(
        "\n".join(lines), encoding="utf-8")
    lines_md = [
        "QCFP-MTF PHASE 4 GOVERNANCE CLOSURE RECORD",
        "================================================",
        "",
        f"Verdict      : {verdict}",
        f"Freeze State : {_freeze_state(verdict)}",
        "",
    ]
    for key, value in close_record.items():
        lines_md.append(f"{key:<32} {value}")
    lines_md += ["", "Gate 明细："]
    for name, gate in results.items():
        lines_md.append(f"- {name} [{gate.get('priority')}]: "
                        f"{gate.get('status')} / {gate.get('verdict')}")
    (out_dir / "phase4_acceptance.md").write_text(
        "\n".join(lines_md), encoding="utf-8")
    return acceptance


def phase4_gate() -> dict:
    acceptance = phase4_acceptance()
    return {"gate": "PHASE4_GATE",
            "verdict": acceptance["verdict"],
            "pass": acceptance["pass"],
            "failures": acceptance["failures"],
            "missing_evidence": acceptance["missing_evidence"],
            "freeze_state": acceptance["freeze_state"]}
