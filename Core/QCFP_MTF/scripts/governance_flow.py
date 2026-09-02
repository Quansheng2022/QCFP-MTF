#!/usr/bin/env python
# coding: utf-8
"""QCFP-MTF 流程治理流水线（Flow Governance Engineering）

把 10 项流程治理接入开发主流程：
    1 spec                Canonical Spec 一致性审计（spec_conformance）
    2 baseline-init       创建 Canonical Baseline（Create-Only）
    3 baseline-check      Baseline 重算比对（PASS / BASELINE_CHANGED）
    4 traceability        Traceability Manifest 三类孤儿审计
    5 contract-impl       校验 Implementation Contract + Scope Checker
    6 contract-accept     校验 Acceptance Contract + 结果比对
    7 impact              生成 Change Impact Classification
    8 review              Evidence-Aware Review Report
    9 patch-audit         DeepSeek Patch Scope Lock 审计
    10 judge              Pure Release Judge（三态判定）
    11 promote            两级 Promotion Gate（Qualification / Promotion）

用法示例：
    python Core/QCFP_MTF/scripts/governance_flow.py spec
    python Core/QCFP_MTF/scripts/governance_flow.py baseline-init
    python Core/QCFP_MTF/scripts/governance_flow.py baseline-check
    python Core/QCFP_MTF/scripts/governance_flow.py traceability
    python Core/QCFP_MTF/scripts/governance_flow.py impact change.json
    python Core/QCFP_MTF/scripts/governance_flow.py judge audit/bundle
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.common.paths import get_project_root


AUDIT_DIR = get_project_root() / "audit"


def _load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def cmd_spec(args) -> int:
    from QCFP_MTF.governance.canonical_spec import spec_conformance_artifact
    result = spec_conformance_artifact(AUDIT_DIR)
    print(f"Canonical Spec Conformance: {result['verdict']}")
    return 0 if result["conformant"] else 1


def cmd_baseline_init(args) -> int:
    from QCFP_MTF.governance.governance_baseline import (
        compute_baseline, write_baseline,
    )
    baseline = compute_baseline()
    result = write_baseline(baseline)
    print(f"Baseline Init: {'FROZEN' if result['frozen'] else 'SKIP_EXISTS'}"
          f" -> {result.get('path', '')}")
    if not result["frozen"]:
        # Create-Only：已存在 = 已完成初始化（write_baseline 仍拒绝覆盖）
        print(f"  {result['reason']}")
    return 0


def cmd_baseline_check(args) -> int:
    from QCFP_MTF.governance.governance_baseline import baseline_artifact
    result = baseline_artifact(AUDIT_DIR / "baseline")
    print(f"Baseline Gate: {result['verdict']}")
    if result.get("drift"):
        for k, v in result["drift"].items():
            print(f"  drift {k}: {v['frozen']} != {v['current']}")
    return 0 if result["pass"] else 1


def cmd_baseline_candidate(args) -> int:
    from QCFP_MTF.governance.governance_baseline import (
        create_baseline_candidate, validate_baseline_candidate,
    )
    created = create_baseline_candidate(AUDIT_DIR / "baseline")
    print(f"Baseline Candidate: "
          f"{'CREATED' if created['created'] else 'SKIP_EXISTS'}"
          f" -> {created.get('path', '')}")
    if not created["created"]:
        print(f"  {created['reason']}")
    validation = validate_baseline_candidate(AUDIT_DIR / "baseline")
    print(f"Baseline Candidate Validation: {validation['verdict']}")
    for k, v in validation["drift_vs_frozen"].items():
        print(f"  drift {k}: {v['frozen']} -> {v['candidate']}")
    return 0 if (created["created"] and validation["valid"]) else 1


def cmd_baseline_approve(args) -> int:
    from QCFP_MTF.governance.governance_baseline import (
        approve_baseline_candidate,
    )
    result = approve_baseline_candidate(
        AUDIT_DIR / "baseline", human_approved=args.human)
    print(f"Baseline Approve: "
          f"{'APPROVED' if result['approved'] else 'REJECTED'}")
    print(f"  {result.get('reason', '')}")
    if result["approved"]:
        print(f"  新 baseline_id: {result['baseline_id']}")
        print(f"  归档: {result.get('archive') or '无（首个 Baseline）'}")
    return 0 if result["approved"] else 1


def cmd_traceability(args) -> int:
    from QCFP_MTF.governance.traceability import traceability_artifact
    audit = traceability_artifact(AUDIT_DIR)
    print(f"Traceability Audit: {audit['verdict']}")
    print(f"  test_index: {audit['test_index_status']}"
          f" ({audit['test_count']} 项)")
    print(f"  p0: {audit['p0_fully_connected']}/{audit['p0_total']} 全连通")
    print(f"  orphan_requirements: {audit['orphan_requirements'] or '无'}")
    print(f"  dangling_test_refs: {audit['dangling_test_references'] or '无'}")
    print(f"  orphan_tests(REVIEW): {len(audit['orphan_tests_review'])}")
    print(f"  ACTIVE orphan capabilities: "
          f"{audit['active_orphan_capabilities'] or '无'}")
    return 0 if not audit["errors"] else 1


def cmd_contract_impl(args) -> int:
    from QCFP_MTF.governance.implementation_contract import (
        bind_change_impact, contract_result_artifact,
        implementation_contract_gate, load_contract,
        validate_implementation_contract,
    )
    contract = load_contract(args.contract)
    validation = validate_implementation_contract(contract)
    if not validation["valid"]:
        print(f"Implementation Contract INVALID: {validation['errors']}")
        return 1
    impact = _load_json(args.change_impact) if args.change_impact else {}
    binding = bind_change_impact(contract, impact)
    if not binding["bound"]:
        print(f"Implementation Contract INVALID: {binding['mismatches']}")
        return 1
    changed = []
    if args.diff_file:
        changed = _load_json(args.diff_file).get("changed_files", [])
    result = implementation_contract_gate(contract, changed)
    contract_result_artifact(contract, result, AUDIT_DIR)
    print(f"Implementation Contract Gate: {result['verdict']}")
    for v in result["violations"]:
        print(f"  violation {v['kind']}: {v['detail']}")
    return 0 if result["pass"] else 1


def cmd_contract_accept(args) -> int:
    from QCFP_MTF.governance.acceptance_contract import (
        acceptance_gate, acceptance_result_artifact, load_contract,
        validate_acceptance_contract,
    )
    contract = load_contract(args.contract)
    tier = contract.get("change_tier", args.tier)
    validation = validate_acceptance_contract(
        contract, critical_change=tier == "HIGH")
    if not validation["valid"]:
        print(f"Acceptance Contract INVALID: {validation['errors']}")
        return 1
    results = _load_json(args.results) if args.results else {}
    gate = acceptance_gate(contract, results,
                           critical_change=tier == "HIGH")
    acceptance_result_artifact(contract, gate, AUDIT_DIR)
    print(f"Acceptance Contract Gate: {gate['verdict']}")
    if gate.get("evidence_gaps"):
        print(f"  evidence_gaps: {gate['evidence_gaps']}")
    if gate.get("failures"):
        print(f"  failures: {gate['failures']}")
    return 0 if gate["pass"] else 1


def cmd_impact(args) -> int:
    from QCFP_MTF.governance.change_impact_classification import (
        write_change_impact_record,
    )
    change = _load_json(args.change)
    diff_evidence = _load_json(args.diff_file)
    record = write_change_impact_record(change, args.out, diff_evidence)
    impact = record["impact"]
    print(f"Change Impact: status={impact.get('status')} "
          f"tier={impact.get('tier')} "
          f"(declared={impact.get('declared_tier')}, "
          f"observed={impact.get('observed_tier')})")
    print(f"  critical={impact['critical_areas']}")
    print(f"  validation: {impact['validation_requirements']}")
    print(f"  approved_for_contract: {impact.get('approved_for_contract')}")
    return 0 if impact.get("status") == "CHANGE_IMPACT_READY" else 1


def cmd_review(args) -> int:
    from QCFP_MTF.governance.evidence_aware_review import review_artifact
    review = _load_json(args.review)
    report = review_artifact(review, AUDIT_DIR)
    print(f"Evidence-Aware Review: {report.get('verdict')}")
    critical = [f for f in report.get("findings") or []
                if f.get("severity") == "CRITICAL"
                and f.get("category") != "NO_ISSUE"]
    if critical:
        print(f"  CRITICAL findings 未解决: "
              f"{[f['finding_id'] for f in critical]}")
        return 1
    return 0 if report.get("verdict") != "REVIEW_INVALID" else 1


def cmd_review_resolve(args) -> int:
    from QCFP_MTF.governance.evidence_aware_review import (
        review_resolution_artifact,
    )
    report = _load_json(args.review)
    resolutions = _load_json(args.resolutions)
    resolution = review_resolution_artifact(report, resolutions, AUDIT_DIR)
    gate = resolution["gate"]
    print(f"Review Resolution: {gate['verdict']} "
          f"(open_critical={resolution['open_critical']}, "
          f"open_major={resolution['open_major']})")
    return 0 if gate["allowed"] else 1


def cmd_patch_audit(args) -> int:
    from QCFP_MTF.governance.patch_scope_lock import (
        load_patch_contract, scope_audit_artifact,
    )
    contract = load_patch_contract(args.contract)
    patch_evidence = _load_json(args.evidence)
    before = _load_json(args.before) if args.before else None
    after = _load_json(args.after) if args.after else None
    manifest_after = _load_json(args.manifest_after) \
        if args.manifest_after else None
    audit = scope_audit_artifact(
        contract, patch_evidence, AUDIT_DIR, before, after,
        feature_manifest_after=manifest_after)
    print(f"Patch Scope Lock: {audit['verdict']}")
    for v in audit["violations"]:
        print(f"  violation {v['kind']}: {v['detail']}")
    return 0 if audit["verdict"] == "PATCH_ACCEPTED" else 1


def cmd_judge(args) -> int:
    from QCFP_MTF.governance.pure_release_judge import (
        release_verdict_artifact,
    )
    bundle_dir = Path(args.bundle_dir)
    bundle = {}
    for p in bundle_dir.glob("*.json"):
        if p.name == "evidence_manifest.json":
            continue
        bundle[p.name] = _load_json(p)
    manifest = None
    manifest_path = bundle_dir / "evidence_manifest.json"
    if manifest_path.exists():
        manifest = _load_json(manifest_path)
    if manifest is None:
        print("Pure Release Judge: NOT_PROVEN "
              "（缺少 evidence_manifest.json，先运行 evidence-pack）")
        return 1
    verdict = release_verdict_artifact(bundle, AUDIT_DIR,
                                       evidence_manifest=manifest)
    print(f"Pure Release Judge: {verdict['verdict']}")
    for key in ("missing_artifacts", "failed_artifacts",
                "indeterminate_artifacts", "identity_violations"):
        if verdict.get(key):
            print(f"  {key}: {verdict[key]}")
    return 0 if verdict["verdict"] == "SOFTWARE_QUALIFIED" else 1


def cmd_evidence_pack(args) -> int:
    from QCFP_MTF.governance.pure_release_judge import (
        build_evidence_manifest,
    )
    result = build_evidence_manifest(
        args.bundle_dir, args.change_id, args.release_id,
        args.baseline_id, args.bundle_dir)
    manifest = result.get("manifest")
    if manifest is None:
        print(f"Evidence Pack: {result['pack_status']} "
              f"（{result.get('reason', '')}）")
        for key in ("rejected", "missing_identity"):
            if result.get(key):
                print(f"  {key}: {result[key]}")
        return 1
    print(f"Evidence Pack: PACK_ACCEPTED "
          f"({len(manifest['artifacts'])} artifacts, "
          f"bundle_hash={manifest['bundle_hash'][:12]}...)")
    print("  Read-Only：输入 artifact 未被修改（身份只验证、不盖章）")
    return 0


def cmd_promote(args) -> int:
    from QCFP_MTF.governance.qualification_promotion import (
        promotion_verdict_artifact,
    )
    evidence = _load_json(args.evidence) if args.evidence else {}
    if args.evidence_manifest:
        evidence = dict(evidence)
        evidence["evidence_manifest"] = _load_json(args.evidence_manifest)
    if args.release_verdict:
        evidence = dict(evidence)
        evidence["release_verdict"] = _load_json(args.release_verdict)
    human_approval = _load_json(args.human_approval) \
        if args.human_approval else None
    if human_approval is not None:
        evidence = dict(evidence)
        evidence["human_approval"] = human_approval
    context = {"change_id": args.change_id,
               "release_id": args.release_id,
               "baseline_id": args.baseline_id}
    verdict = promotion_verdict_artifact(
        args.from_state, args.to_state, evidence, context, AUDIT_DIR)
    print(f"Promotion Verdict: {verdict['verdict']}")
    gate = verdict.get("gate") or {}
    if gate.get("failed"):
        print(f"  blocked: {gate['failed']}")
    return 0 if verdict["verdict"] == "PROMOTION_OK" else 1


def cmd_phase1(args) -> int:
    """Phase 1 — Architecture & Specification Freeze（7 Sprint 收口）。"""
    from QCFP_MTF.governance.phase1 import phase1_acceptance
    acceptance = phase1_acceptance()
    print(f"Phase 1 Acceptance: {acceptance['verdict']}")
    for key, value in acceptance["freeze_stamp"].items():
        print(f"  {key:<28} {value}")
    if acceptance["failures"]:
        print(f"  失败 Gate: {acceptance['failures']}")
    print(f"  Acceptance Pack: audit/phase1/phase1_acceptance.json")
    return 0 if acceptance["pass"] else 1


def cmd_phase4(args) -> int:
    """Phase 4 — Flow Governance Closure（FGC-1 + SF-1~SF-5 + Zero-Bypass）。"""
    from QCFP_MTF.governance.phase4 import phase4_acceptance
    acceptance = phase4_acceptance()
    print(f"Phase 4 Acceptance: {acceptance['verdict']}")
    print(f"  Freeze State: {acceptance['freeze_state']}")
    for key, value in acceptance["close_record"].items():
        print(f"  {key:<32} {value}")
    if acceptance["failures"]:
        print(f"  失败 Gate: {acceptance['failures']}")
    if acceptance["missing_evidence"]:
        print(f"  缺证据: {acceptance['missing_evidence']}")
    print(f"  Acceptance Pack: audit/phase4/phase4_acceptance.json")
    return 0 if acceptance["pass"] else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF 流程治理流水线")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("spec", help="Canonical Spec 一致性审计")
    sub.add_parser("baseline-init", help="创建 Canonical Baseline（Create-Only）")
    sub.add_parser("baseline-check", help="Baseline 重算比对")
    sub.add_parser("baseline-candidate",
                   help="创建并校验新 Baseline Candidate")
    sub.add_parser("traceability", help="Traceability 三类孤儿审计")
    sub.add_parser("phase1", help="Phase 1 Freeze Gate（Spec/Architecture/"
                                  "Authority/Traceability/Baseline）")
    sub.add_parser("phase4", help="Phase 4 Flow Governance Closure Gate"
                                  "（FGC-1 + SF-1~SF-5 + Zero-Bypass）")

    p = sub.add_parser("baseline-approve",
                       help="Human 批准 Candidate 成为新 Frozen Baseline")
    p.add_argument("--human", action="store_true",
                   help="Human 授权（AI 无权批准 Baseline）")

    p = sub.add_parser("contract-impl", help="Implementation Contract 校验")
    p.add_argument("contract")
    p.add_argument("--change-impact", required=True,
                   help="Change Impact Artifact（CHANGE-IMPACT-2），必须绑定")
    p.add_argument("--diff-file", help="git diff 文件清单 JSON")

    p = sub.add_parser("contract-accept", help="Acceptance Contract 校验")
    p.add_argument("contract")
    p.add_argument("--results", help="测试结果 JSON")
    p.add_argument("--tier", default="STANDARD",
                   choices=("LOW", "STANDARD", "HIGH"))

    p = sub.add_parser("impact", help="Change Impact Classification")
    p.add_argument("change")
    p.add_argument("--out", default=str(AUDIT_DIR / "change_impact.json"))
    p.add_argument(
        "--diff-file", required=True,
        help="Observed Diff Evidence（OBSERVED-DIFF-2）；"
             "Production Change Impact 必填")

    p = sub.add_parser("review", help="Evidence-Aware Review")
    p.add_argument("review")

    p = sub.add_parser("review-resolve", help="Review Resolution 收口")
    p.add_argument("review")
    p.add_argument("resolutions")

    p = sub.add_parser("patch-audit",
                       help="DeepSeek Patch Scope Lock（独立证据强制）")
    p.add_argument("contract")
    p.add_argument("evidence", help="patch_evidence.json（PATCH-EVIDENCE-2）")
    p.add_argument("--before", required=True,
                   help="authority_graph_before.json")
    p.add_argument("--after", required=True,
                   help="authority_graph_after.json")
    p.add_argument("--manifest-after", required=True,
                   help="candidate feature manifest（after）")

    p = sub.add_parser("judge", help="Pure Release Judge")
    p.add_argument("bundle_dir")

    p = sub.add_parser("evidence-pack", help="生成 evidence_manifest.json")
    p.add_argument("bundle_dir")
    p.add_argument("--change-id", required=True)
    p.add_argument("--release-id", required=True)
    p.add_argument("--baseline-id", required=True)

    p = sub.add_parser("promote", help="两级 Promotion Gate")
    p.add_argument("--from-state", default="DEVELOPMENT")
    p.add_argument("--to-state", required=True)
    p.add_argument("--change-id", default="")
    p.add_argument("--release-id", default="")
    p.add_argument("--baseline-id", default="")
    p.add_argument("--evidence", help="本步 Gate 所需证据 JSON"
                                      "（Gate A 传 release_verdict.json）")
    p.add_argument("--release-verdict", help="release_verdict.json"
                                             "（Approval hash 绑定用）")
    p.add_argument("--evidence-manifest", help="evidence_manifest.json"
                                               "（Approval hash 绑定用）")
    p.add_argument("--human-approval", help="Human Approval 对象 JSON"
                                            "（仅 HUMAN_APPROVED / "
                                            "PRODUCTION_DSS 需要）")

    args = parser.parse_args(argv)
    handler = {
        "spec": cmd_spec,
        "baseline-init": cmd_baseline_init,
        "baseline-check": cmd_baseline_check,
        "baseline-candidate": cmd_baseline_candidate,
        "baseline-approve": cmd_baseline_approve,
        "traceability": cmd_traceability,
        "phase1": cmd_phase1,
        "phase4": cmd_phase4,
        "contract-impl": cmd_contract_impl,
        "contract-accept": cmd_contract_accept,
        "impact": cmd_impact,
        "review": cmd_review,
        "review-resolve": cmd_review_resolve,
        "patch-audit": cmd_patch_audit,
        "judge": cmd_judge,
        "evidence-pack": cmd_evidence_pack,
        "promote": cmd_promote,
    }
    return handler[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
