#!/usr/bin/env python
# coding: utf-8
"""Phase 4 Evidence Builder（CS-70 变更流程 + FGC Evidence 生成）

只做 Evidence Generation（Phase 4 Development 的一部分）：
    1. Observed Diff（OBSERVED-DIFF-2，git 真实 diff）
    2. Change Impact（CHANGE-IMPACT-2）
    3. Implementation Contract Gate + Acceptance Contract Gate
    4. Patch Scope Audit（PATCH-EVIDENCE-2 + Authority Graph before/after
       + Feature Manifest after）
    5. Evidence-Aware Review + Resolution
    6. SF-5 Promotion 阻断检查（AI approval / 旧 Release / hash mismatch）
    7. Evidence Pack（SF-3 只读）→ evidence_manifest.json
    8. Manifest + Identity Verification（SF-4）

Builder 无权签发 Verdict / 无权执行 Human Approval
（QCFP-SPEC-RLS-004）；Phase 4 Acceptance 由 governance/phase4.py 聚合，
冻结由 Human 决定。

用法（在项目根执行，先运行 phase4_regression_runner）：
    python Core/QCFP_MTF/scripts/phase4_evidence_builder.py \
        --base-commit cdcab0c \
        --change-id CHG-P4-FGC-1 \
        --release-id FGC-CLOSURE-1 \
        --baseline-id GOV-BASELINE-4 \
        --graph-before Temp/phase4_evidence/graphs/authority_graph_before.json \
        --graph-after Temp/phase4_evidence/graphs/authority_graph_after.json
"""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001 - 非 UTF-8 控制台降级
    pass

from QCFP_MTF.governance.acceptance_contract import (  # noqa: E402
    acceptance_gate,
    acceptance_result_artifact,
    load_contract as load_acceptance_contract,
)
from QCFP_MTF.governance.canonical_spec import spec_conformance  # noqa: E402
from QCFP_MTF.governance.change_impact_classification import (  # noqa: E402
    change_impact_record,
)
from QCFP_MTF.governance.evidence_aware_review import (  # noqa: E402
    review_artifact,
    review_report,
    review_resolution_artifact,
)
from QCFP_MTF.governance.governance_baseline import baseline_gate  # noqa: E402
from QCFP_MTF.governance.implementation_contract import (  # noqa: E402
    bind_change_impact,
    contract_result_artifact,
    implementation_contract_gate,
    load_contract as load_impl_contract,
)
from QCFP_MTF.governance.minimal_trusted_release import (  # noqa: E402
    FROZEN_PRODUCTION_MANIFEST,
)
from QCFP_MTF.governance.patch_scope_lock import (  # noqa: E402
    audit_patch_scope,
    load_patch_contract,
)
from QCFP_MTF.governance.pure_release_judge import (  # noqa: E402
    build_evidence_manifest,
    validate_artifact_identity,
    verify_evidence_manifest,
)
from QCFP_MTF.governance.qualification_promotion import (  # noqa: E402
    promotion_verdict,
)
from QCFP_MTF.governance.traceability import audit_traceability  # noqa: E402


IDENTITY_FIELDS = ("change_id", "release_id", "baseline_id")

REQUIRED_REGRESSION_SUITES = (
    "phase4_flow", "bypass", "phase1", "phase3",
    "decision", "governance", "golden", "full_core",
)

ACCEPTANCE_CATEGORIES = ("positive", "boundary", "negative", "adversarial")


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                    encoding="utf-8")


def _stamp(data: dict, identity: dict) -> dict:
    data = dict(data)
    for field in IDENTITY_FIELDS:
        data[field] = identity.get(field, "")
    return data


def _git_changed_files(base: str, root: Path) -> tuple:
    """Observed Diff：git diff base..HEAD（无 commit 时回退工作树）。"""
    proc = subprocess.run(
        ["git", "-c", "core.quotepath=false",
         "diff", "--name-only", base, "HEAD"],
        cwd=str(root), capture_output=True)
    raw = proc.stdout.decode("utf-8", "replace") if proc.stdout else ""
    files = [f for f in raw.splitlines() if f.strip()]
    if not files:
        proc = subprocess.run(
            ["git", "-c", "core.quotepath=false",
             "diff", "--name-only", base],
            cwd=str(root), capture_output=True)
        raw = proc.stdout.decode("utf-8", "replace") \
            if proc.stdout else ""
        files = [f for f in raw.splitlines() if f.strip()]
    diff = subprocess.run(
        ["git", "-c", "core.quotepath=false", "diff", base, "HEAD"],
        cwd=str(root), capture_output=True)
    diff_bytes = diff.stdout or b""
    if not files and not diff_bytes.strip():
        proc = subprocess.run(
            ["git", "-c", "core.quotepath=false", "diff", base],
            cwd=str(root), capture_output=True)
        diff_bytes = proc.stdout or b""
    return sorted(files), _sha256_bytes(diff_bytes)


def _git_show_file(ref: str, rel: str, root: Path) -> bytes:
    proc = subprocess.run(
        ["git", "show", f"{ref}:{rel}"], cwd=str(root),
        capture_output=True)
    return proc.stdout


def _schema_hash(source_ref: str, root: Path) -> str:
    """决策 Schema 哈希（versions.py + schema registry/contract 内容）。"""
    paths = (
        "Core/QCFP_MTF/decision/versions.py",
        "Core/QCFP_MTF/decision/schema_registry.py",
        "Core/QCFP_MTF/decision/schema_contract.py",
    )
    chunks = []
    for rel in paths:
        raw = _git_show_file(source_ref, rel, root)
        chunks.append(f"{rel}\0{_sha256_bytes(raw)}")
    return _sha256_bytes("\n".join(chunks).encode("utf-8"))


def _check_blocked(name: str, verdict: dict) -> bool:
    ok = verdict.get("verdict") == "PROMOTION_BLOCKED"
    print(f"  {name}: {'BLOCKED' if ok else verdict.get('verdict')}")
    return ok


def _promotion_checks() -> dict:
    """SF-5：三个 Promotion Bypass 阻断语义检查（机器执行）。"""
    from QCFP_MTF.tests.test_governance.test_flow_governance import (
        _human_approval_artifact,
        _promotion_context,
        _promotion_evidence,
        _release_verdict_artifact,
    )
    context = _promotion_context()
    evidence = _promotion_evidence()
    old = dict(_release_verdict_artifact(), release_id="REL-OLD")
    c1 = _check_blocked(
        "old_release_qualification",
        promotion_verdict("DEVELOPMENT", "SOFTWARE_QUALIFIED",
                          old, context))
    ai = _human_approval_artifact(evidence, actor_type="AI")
    c2 = _check_blocked(
        "ai_human_approval",
        promotion_verdict("PRODUCTION_ELIGIBLE", "HUMAN_APPROVED",
                          {"human_approval": ai, **evidence}, context))
    approval = _human_approval_artifact(evidence)
    approval["release_verdict_hash"] = "wrong"
    c3 = _check_blocked(
        "approval_hash_mismatch",
        promotion_verdict("PRODUCTION_ELIGIBLE", "HUMAN_APPROVED",
                          {"human_approval": approval, **evidence},
                          context))
    return {
        "old_release_qualification_blocked": c1,
        "ai_human_approval_blocked": c2,
        "approval_hash_mismatch_blocked": c3,
    }


def _hash_files(bundle_dir: Path) -> dict:
    hashes = {}
    for p in sorted(bundle_dir.glob("*.json")):
        if p.name == "evidence_manifest.json":
            continue
        hashes[p.name] = _sha256_bytes(p.read_bytes())
    return hashes


def _suite_ok(suite: dict) -> bool:
    """机械布尔运算：suite 必须 PASS 且 counts 自洽（无 skipped/failed）。"""
    try:
        collected = int(suite.get("collected") or 0)
        passed = int(suite.get("passed") or 0)
        failed = int(suite.get("failed") or 0)
        errors = int(suite.get("errors") or 0)
        skipped = int(suite.get("skipped") or 0)
    except (TypeError, ValueError):
        return False
    return (
        suite.get("status") == "PASS"
        and collected > 0
        and collected == passed + failed + errors + skipped
        and failed == 0 and errors == 0 and skipped == 0
    )


def _validate_regression_payload(regression: dict) -> tuple:
    """Test System 事实校验：verdict PASS 且全部 required suite PASS。"""
    suites = regression.get("suites") or {}
    problems = []
    if regression.get("verdict") != "PASS":
        problems.append(f"regression verdict = "
                        f"{regression.get('verdict')} != PASS")
    missing = [
        s for s in REQUIRED_REGRESSION_SUITES
        if s not in suites]
    if missing:
        problems.append(f"missing suites: {missing}")
    for name in REQUIRED_REGRESSION_SUITES:
        if name in suites and not _suite_ok(suites[name]):
            problems.append(f"suite {name} 未 PASS/自洽")
    return problems


def _validate_case_results(case_evidence: dict) -> list:
    """Acceptance Case Evidence 必须来自 Test System 且全部通过。"""
    problems = []
    if case_evidence.get("schema") != \
            "PHASE4-ACCEPTANCE-CASE-RESULTS-1":
        problems.append("case evidence schema != "
                        "PHASE4-ACCEPTANCE-CASE-RESULTS-1")
    if case_evidence.get("verdict") != "PASS":
        problems.append(f"case evidence verdict = "
                        f"{case_evidence.get('verdict')} != PASS")
    categories = case_evidence.get("categories") or {}
    for category in ACCEPTANCE_CATEGORIES:
        cat = categories.get(category) or {}
        if cat.get("status") != "PASS":
            problems.append(f"category {category} status = "
                            f"{cat.get('status')} != PASS")
        if int(cat.get("expected") or 0) <= 0:
            problems.append(f"category {category} expected <= 0")
        if int(cat.get("expected") or -1) != int(cat.get("executed") or -2):
            problems.append(f"category {category} expected != executed")
        if int(cat.get("failed") or 0) or int(cat.get("errors") or 0) \
                or int(cat.get("skipped") or 0):
            problems.append(f"category {category} 存在 failed/errors/skipped")
    return problems


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase 4 Evidence Builder")
    parser.add_argument("--base-commit", required=True)
    parser.add_argument("--change-id", required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--baseline-id", required=True)
    parser.add_argument("--out",
                        default=str(PROJECT_ROOT / "audit" / "phase4"))
    parser.add_argument("--contracts",
                        default=str(
                            PROJECT_ROOT / "audit" / "phase4" / "contracts"))
    parser.add_argument("--graph-before", required=True)
    parser.add_argument("--graph-after", required=True)
    parser.add_argument("--regression-summary",
                        default=str(
                            PROJECT_ROOT / "audit" / "phase4" /
                            "phase4_regression_summary.json"))
    parser.add_argument("--case-results",
                        default=str(
                            PROJECT_ROOT / "audit" / "phase4" /
                            "phase4_acceptance_case_results.json"))
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    bundle_dir = out_dir / "bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    contract_dir = Path(args.contracts)
    identity = {"change_id": args.change_id,
                "release_id": args.release_id,
                "baseline_id": args.baseline_id}
    root = PROJECT_ROOT

    # ---- 1. Observed Diff（OBSERVED-DIFF-2） ---------------------------
    changed_files, diff_hash = _git_changed_files(args.base_commit, root)
    if not changed_files:
        print("ERROR: Observed Diff 为空（base 与 HEAD 无差异）")
        return 1
    source_commit = args.base_commit
    target_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(root),
        capture_output=True).stdout.decode("utf-8", "replace").strip() \
        or "WORKTREE"
    observed_diff = {
        "schema": "OBSERVED-DIFF-2",
        "source_commit": source_commit,
        "target_commit": target_commit,
        "diff_hash": diff_hash,
        "changed_files": changed_files,
        "generator": "phase4-evidence-builder",
        "generator_version": "1",
    }
    _write_json(out_dir / "observed_diff.json", observed_diff)
    print(f"Observed Diff: {len(changed_files)} files, "
          f"source={source_commit} target={target_commit}")

    # ---- 2. Change Impact（CHANGE-IMPACT-2） ---------------------------
    change = {
        "change_id": args.change_id,
        "change_type": "modify",
        "description": "Phase 4 FGC Closure（Spec + Gate + Runner + "
                       "Evidence Builder + CLI + tests）",
        "touches": ["Governance", "Tests", "Docs"],
        "source_commit": source_commit,
    }
    impact = change_impact_record(change, observed_diff)["impact"]
    if impact.get("approved_for_contract") is not True:
        print(f"ERROR: change impact 未 approved: "
              f"{impact.get('status')} {impact.get('reason', '')}")
        return 1
    _write_json(bundle_dir / "change_impact.json",
                _stamp(impact, identity))
    print(f"Change Impact: tier={impact.get('tier')} "
          f"observed_tier={impact.get('observed_tier')} "
          f"diff_status={impact.get('diff_status')}")

    # ---- 3. Contracts（Implementation + Acceptance） ------------------
    impl_contract = load_impl_contract(
        contract_dir / "implementation_contract.json")
    binding = bind_change_impact(impl_contract, impact)
    if not binding["bound"]:
        print(f"ERROR: contract 未绑定 change impact: "
              f"{binding['mismatches']}")
        return 1
    impl_gate = implementation_contract_gate(
        impl_contract, changed_files)
    contract_result_artifact(impl_contract, impl_gate, bundle_dir)
    _write_json(
        bundle_dir / "implementation_contract_result.json",
        _stamp(json.loads(
            (bundle_dir / "implementation_contract_result.json")
            .read_text(encoding="utf-8")), identity))
    if impl_gate["verdict"] != "CONTRACT_OK":
        print(f"ERROR: implementation contract gate: "
              f"{impl_gate['violations']}")
        return 1
    print("Implementation Contract Gate: CONTRACT_OK")

    # ---- 基础 Gate 证据（Spec / Baseline / Traceability） ------------
    # 先于 Acceptance 计算：invariants / unchanged 必须由真实 Gate 结果推导，
    # 不得硬编码 True（IMPLEMENTATION_DEFECT 修复）。
    spec_evidence = spec_conformance()
    baseline_evidence = dict(baseline_gate())
    baseline_evidence.setdefault("schema", "BASELINE-GATE-2")
    trace_evidence = audit_traceability()
    for name, data in (
            ("spec_conformance.json", spec_evidence),
            ("baseline.json", baseline_evidence),
            ("traceability.json", trace_evidence)):
        _write_json(bundle_dir / name, _stamp(data, identity))
    print("Spec / Baseline / Traceability evidence written")

    regression_path = Path(args.regression_summary)
    if not regression_path.exists():
        print(f"ERROR: regression summary 缺失（先运行 Test System）: "
              f"{regression_path}")
        return 1
    regression = json.loads(
        regression_path.read_text(encoding="utf-8"))
    regression_problems = _validate_regression_payload(regression)
    if regression_problems:
        print(f"ERROR: regression evidence 未满足 PASS/NOT_PROVEN 语义: "
              f"{regression_problems}")
        return 1

    # Golden = Test System 原样投影（P1-EVID-01）：
    # n_failed/status 不得由 Builder 构造；Test System status 原样保留。
    golden_suite = (regression.get("suites") or {}).get("golden") or {}
    golden = {
        "n_total": int(golden_suite.get("collected") or 0),
        "n_failed": int(golden_suite.get("failed") or 0)
        + int(golden_suite.get("errors") or 0),
        "n_skipped": int(golden_suite.get("skipped") or 0),
        "status": golden_suite.get("status"),
        "results": golden_suite.get("failures") or [],
        "source_artifact": "phase4_regression_summary.json",
        "source_suite": "golden",
        "generated_by": "EVIDENCE_BUILDER",
        "evidence_authority": "TEST_SYSTEM",
    }
    _write_json(
        bundle_dir / "golden_evidence.json",
        _stamp({
            "schema": "PHASE4-GOLDEN-EVIDENCE-1",
            "golden": golden,
            "rule": "Golden 只投影 Test System 的 golden suite 事实",
        }, identity))

    case_results_path = Path(args.case_results)
    if not case_results_path.exists():
        print(f"ERROR: acceptance case results 缺失"
              f"（先运行 Test System）: {case_results_path}")
        return 1
    case_evidence = json.loads(
        case_results_path.read_text(encoding="utf-8"))
    case_problems = _validate_case_results(case_evidence)
    if case_problems:
        print(f"ERROR: acceptance case evidence 未满足 PASS 语义: "
              f"{case_problems}")
        return 1
    _write_json(
        bundle_dir / "acceptance_case_evidence.json",
        _stamp({
            "schema": "PHASE4-ACCEPTANCE-CASE-EVIDENCE-1",
            "categories": {
                k: {kk: vv for kk, vv in v.items() if kk != "cases"}
                for k, v in (case_evidence.get("categories") or {}).items()
            },
            "source_artifact": "phase4_acceptance_case_results.json",
            "generated_by": "EVIDENCE_BUILDER",
            "evidence_authority": "TEST_SYSTEM",
            "rule": "Builder 只投影 Test System 的逐 case 事实，"
                    "不计算、不改写结果",
        }, identity))

    accept_contract = load_acceptance_contract(
        contract_dir / "acceptance_contract.json")
    accept_results = {
        "positive_cases": [], "boundary_cases": [],
        "negative_cases": [], "adversarial_cases": [],
        "golden": golden,
        "invariants": [spec_evidence.get("conformant") is True,
                       baseline_evidence.get("pass") is True,
                       trace_evidence.get("pass") is True],
        "unchanged": [not any(
            f.startswith("Core/QCFP_MTF/decision/")
            for f in changed_files)],
        "decision_deltas": {},
    }
    accept_gate = acceptance_gate(accept_contract, accept_results)
    acceptance_result_artifact(accept_contract, accept_gate, bundle_dir)
    _write_json(
        bundle_dir / "acceptance_result.json",
        _stamp(json.loads(
            (bundle_dir / "acceptance_result.json")
            .read_text(encoding="utf-8")), identity))
    if accept_gate["verdict"] != "ACCEPTANCE_PASS":
        print(f"ERROR: acceptance gate: {accept_gate['verdict']} "
              f"{accept_gate.get('failures')} "
              f"{accept_gate.get('evidence_gaps')}")
        return 1
    print(f"Acceptance Gate: ACCEPTANCE_PASS (golden from TEST_SYSTEM, "
          f"n_total={golden['n_total']}, status={golden['status']}, "
          f"case_categories=PASS)")

    # ---- 4. Patch Scope Audit（SF-2） ---------------------------------
    schema_before = _schema_hash(source_commit, root)
    schema_after = _schema_hash(target_commit, root)
    golden_changed = subprocess.run(
        ["git", "-c", "core.quotepath=false",
         "diff", "--name-only", source_commit, "HEAD", "--",
         "Core/QCFP_MTF/tests/golden"], cwd=str(root),
        capture_output=True).stdout.decode("utf-8", "replace").strip()
    patch_evidence = {
        "schema": "PATCH-EVIDENCE-2",
        "diff_hash": diff_hash,
        "changed_files": changed_files,
        "changed_functions": [],
        "import_delta": [],
        "schema_delta": {"hash_before": schema_before,
                         "hash_after": schema_after},
        "golden_delta": {
            "changed_count": 0 if not golden_changed else -1},
        "generator": "phase4-evidence-builder",
    }
    graph_before = json.loads(
        Path(args.graph_before).read_text(encoding="utf-8"))
    graph_after = json.loads(
        Path(args.graph_after).read_text(encoding="utf-8"))
    patch_contract = load_patch_contract(
        contract_dir / "patch_contract.json")
    scope = audit_patch_scope(
        patch_contract, patch_evidence, graph_before, graph_after,
        feature_manifest_after=FROZEN_PRODUCTION_MANIFEST)
    _write_json(bundle_dir / "scope_audit.json",
                _stamp(scope, identity))
    if scope["verdict"] != "PATCH_ACCEPTED":
        print(f"ERROR: patch scope audit: {scope['violations']}")
        return 1
    print(f"Patch Scope Audit: PATCH_ACCEPTED "
          f"(authority_delta={scope['authority_delta']}, "
          f"feature_delta={scope['active_feature_delta']})")

    # ---- 5. Review + Resolution（C7） ---------------------------------
    review_input = json.loads(
        (contract_dir / "review_input.json").read_text(encoding="utf-8"))
    report = review_report(review_input)
    if report["verdict"] == "REVIEW_INVALID":
        print(f"ERROR: review input invalid: "
              f"{report['invalid_findings']}")
        return 1
    review_artifact(review_input, bundle_dir)
    _write_json(bundle_dir / "review_report.json",
                _stamp(json.loads(
                    (bundle_dir / "review_report.json")
                    .read_text(encoding="utf-8")), identity))
    resolutions = json.loads(
        (contract_dir / "review_resolutions.json")
        .read_text(encoding="utf-8"))
    review_resolution_artifact(report, resolutions, bundle_dir)
    _write_json(bundle_dir / "review_resolution.json",
                _stamp(json.loads(
                    (bundle_dir / "review_resolution.json")
                    .read_text(encoding="utf-8")), identity))
    print(f"Review: {report['verdict']} "
          f"({report.get('n_findings')} findings)")

    # ---- SF-5：Promotion Identity 阻断检查 ----------------------------
    checks = _promotion_checks()
    bypass_suite = {
        "schema": "FGC-BYPASS-SUITE-1",
        "all_blocked": all(checks.values()),
        "checks": checks,
        "test_source": "Core/QCFP_MTF/tests/test_governance/"
                       "test_governance_bypass.py",
        "rule": "Promotion Bypass（AI approval / 旧 Release / hash "
                "mismatch）必须全部 PROMOTION_BLOCKED",
    }
    _write_json(bundle_dir / "fgc_bypass_suite.json",
                _stamp(bypass_suite, identity))
    if not bypass_suite["all_blocked"]:
        print("ERROR: SF-5 promotion bypass 未全部阻断")
        return 1
    print("SF-5 Promotion Identity: all blocked")

    # ---- Regression Summary 进 bundle（PHASE4-REGRESSION-1） ----------
    _write_json(bundle_dir / "phase4_regression_summary.json",
                _stamp(regression, identity))

    # ---- 7. Evidence Pack（SF-3 只读） --------------------------------
    before = _hash_files(bundle_dir)
    packed = build_evidence_manifest(
        bundle_dir, args.change_id, args.release_id,
        args.baseline_id, bundle_dir)
    if packed["pack_status"] != "PACK_ACCEPTED":
        print(f"ERROR: evidence pack rejected: "
              f"{packed.get('reason')} {packed.get('missing_identity')}")
        return 1
    after = _hash_files(bundle_dir)
    unchanged = before == after
    readonly_evidence = {
        "schema": "EVIDENCE-PACK-READONLY-1",
        "pack_status": packed["pack_status"],
        "all_unchanged": unchanged,
        "artifact_count": len(before),
        "changed_artifacts": sorted(
            k for k in before if before[k] != after.get(k)),
        "rule": "Packager 只 READ/VERIFY/HASH/INDEX；输入 artifact "
                "sha256 前后必须一致",
    }
    readonly_evidence.update(identity)
    _write_json(out_dir / "evidence_pack_readonly.json",
                readonly_evidence)
    if not unchanged:
        print(f"ERROR: Evidence Pack 修改了 artifact: "
              f"{readonly_evidence['changed_artifacts']}")
        return 1
    print(f"Evidence Pack: PACK_ACCEPTED (artifacts="
          f"{len(before)}, read-only OK)")

    # ---- 8. Manifest + Identity Verification（SF-4） ------------------
    manifest = packed["manifest"]
    bundle = {}
    for p in sorted(bundle_dir.glob("*.json")):
        if p.name == "evidence_manifest.json":
            continue
        bundle[p.name] = json.loads(p.read_text(encoding="utf-8"))
    verify = verify_evidence_manifest(
        bundle, manifest, required=sorted(bundle.keys()))
    expected = identity
    missing_ids, mismatched_ids = [], []
    for name, data in bundle.items():
        result = validate_artifact_identity(data, expected)
        if result["result"] != "PASS":
            (missing_ids if result["result"] == "NOT_PROVEN"
             else mismatched_ids).append(
                {"artifact": name, "reason": result["reason"]})
    manifest_verification = {
        "schema": "EVIDENCE-MANIFEST-VERIFY-1",
        "valid": verify["valid"] and not missing_ids
        and not mismatched_ids,
        "problems": verify["problems"],
        "all_identity_ok": not missing_ids and not mismatched_ids,
        "artifact_count": len(bundle),
        "missing_identity": missing_ids,
        "mismatched_identity": mismatched_ids,
    }
    manifest_verification.update(identity)
    _write_json(out_dir / "evidence_manifest_verification.json",
                manifest_verification)
    if not manifest_verification["valid"]:
        print(f"ERROR: manifest/identity verification failed: "
              f"{verify['problems']} {missing_ids} {mismatched_ids}")
        return 1
    print(f"Manifest + Identity (SF-4): OK "
          f"({manifest_verification['artifact_count']} artifacts)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
