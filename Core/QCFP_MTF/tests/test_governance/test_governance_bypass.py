# coding: utf-8
"""FGC-1 Governance Bypass Test（最终验收 + Surgical Fix Pack 攻击面）

目标不是“函数按设计返回什么”，而是“恶意绕流程是否还能拿到 PASS”：
    Bypass Path to SOFTWARE_QUALIFIED = 0
    Bypass Path to PRODUCTION_DSS     = 0
"""

import hashlib
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_CORE_DIR = _PROJECT_ROOT / "Core"
if str(_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(_CORE_DIR))

from QCFP_MTF.tests.test_governance.test_flow_governance import (
    _acceptance_contract,
    _acceptance_results,
    _contract_base,
    _diff_evidence,
    _graph_after,
    _graph_before,
    _human_approval_artifact,
    _manifest_after,
    _manifest_for,
    _patch_contract,
    _patch_evidence,
    _passing_bundle,
    _promotion_context,
    _promotion_evidence,
    _release_verdict_artifact,
)


# ------------------------- SF-1：Observed Diff Mandatory -------------------

def test_bypass_low_change_without_diff_not_proven():
    from QCFP_MTF.governance.change_impact_classification import (
        effective_change_impact,
    )
    change = {"change_id": "B-1", "change_type": "docs",
              "description": "LOW", "touches": ["Research-only"]}
    impact = effective_change_impact(change, None)
    assert impact["status"] == "CHANGE_IMPACT_NOT_PROVEN"
    assert impact["approved_for_contract"] is False


def test_bypass_declared_low_observed_permission_becomes_high():
    from QCFP_MTF.governance.change_impact_classification import (
        effective_change_impact,
    )
    change = {"change_id": "B-2", "change_type": "docs",
              "description": "伪造 LOW", "touches": ["Research-only"]}
    effective = effective_change_impact(
        change, _diff_evidence(
            ["Core/QCFP_MTF/decision/institutional_permission.py"]))
    assert effective["tier"] == "HIGH"
    assert effective["declared_tier"] == "LOW"
    assert effective["status"] == "CHANGE_IMPACT_READY"


def test_bypass_high_declared_benign_diff_not_downgraded():
    from QCFP_MTF.governance.change_impact_classification import (
        effective_change_impact,
    )
    change = {"change_id": "B-3", "change_type": "modify",
              "description": "HIGH", "touches": ["Permission"]}
    effective = effective_change_impact(
        change, _diff_evidence(["README.md"]))
    assert effective["tier"] == "HIGH"
    assert effective["observed_tier"] == "STANDARD"


# ------------------------- SF-2：Patch Actual Evidence Mandatory ----------

def test_bypass_empty_patch_evidence_not_proven():
    from QCFP_MTF.governance.patch_scope_lock import audit_patch_scope
    result = audit_patch_scope(_patch_contract(), {},
                               _graph_before(), _graph_after(),
                               feature_manifest_after=_manifest_after())
    assert result["verdict"] == "PATCH_NOT_PROVEN"


def test_bypass_missing_authority_graphs_not_proven():
    from QCFP_MTF.governance.patch_scope_lock import audit_patch_scope
    result = audit_patch_scope(
        _patch_contract(),
        _patch_evidence(["Core/QCFP_MTF/decision/engine.py"]),
        None, None, feature_manifest_after=_manifest_after())
    assert result["verdict"] == "PATCH_NOT_PROVEN"


def test_bypass_graph_shows_writer_change_rejected():
    from QCFP_MTF.governance.patch_scope_lock import audit_patch_scope
    after = {"nodes": {
        "decision.engine": {"authority": "NONE"},
        "decision.governance": {"authority": "FINAL_TARGET",
                                "field_writers": ["final_target"]}},
        "roots": {"r": "QCFP_MTF.decision.engine.evaluate"}}
    result = audit_patch_scope(
        _patch_contract(),
        _patch_evidence(["Core/QCFP_MTF/decision/engine.py"]),
        _graph_before(), after, feature_manifest_after=_manifest_after())
    assert result["verdict"] == "PATCH_REJECTED"
    assert result["authority_source"] == "AUTHORITY_GRAPH"


def test_bypass_manifest_shows_new_active_feature_rejected():
    from QCFP_MTF.governance.patch_scope_lock import audit_patch_scope
    result = audit_patch_scope(
        _patch_contract(),
        _patch_evidence(["Core/QCFP_MTF/decision/engine.py"]),
        _graph_before(), _graph_after(),
        feature_manifest_after=_manifest_after(["secret_feature"]))
    assert result["verdict"] == "PATCH_REJECTED"
    assert any(v["kind"] == "FEATURE_SCOPE"
               for v in result["violations"])


# ------------------------- SF-3：Evidence Pack Read-Only -------------------

def test_bypass_packager_cannot_modify_artifacts():
    from QCFP_MTF.governance.pure_release_judge import (
        build_evidence_manifest,
    )
    with __import__("tempfile").TemporaryDirectory() as d:
        bundle_dir = Path(d) / "bundle"
        bundle_dir.mkdir()
        bundle = _passing_bundle()
        bundle["golden_result.json"]["release_id"] = "REL-A"
        bundle["replay_result.json"]["release_id"] = "REL-B"
        before = {}
        for name, data in bundle.items():
            (bundle_dir / name).write_text(
                json.dumps(data, ensure_ascii=False), encoding="utf-8")
            before[name] = hashlib.sha256(
                (bundle_dir / name).read_bytes()).hexdigest()
        result = build_evidence_manifest(
            bundle_dir, "CHG-TEST-001", "REL-1", "GOV-BASELINE-3",
            bundle_dir)
        assert result["pack_status"] == "PACK_REJECTED"
        after = {name: hashlib.sha256(
            (bundle_dir / name).read_bytes()).hexdigest()
            for name in before}
        assert before == after, "Packager 不得改写 artifact identity"


# ------------------------- SF-4：Judge Manifest + Identity ----------------

def test_bypass_manifest_missing_not_proven():
    from QCFP_MTF.governance.pure_release_judge import (
        issue_release_verdict,
    )
    assert issue_release_verdict(_passing_bundle())["verdict"] == "NOT_PROVEN"


def test_bypass_artifact_only_change_id_not_proven():
    from QCFP_MTF.governance.pure_release_judge import (
        issue_release_verdict,
    )
    bundle = _passing_bundle()
    del bundle["golden_result.json"]["release_id"]
    del bundle["golden_result.json"]["baseline_id"]
    manifest = _manifest_for(bundle)
    verdict = issue_release_verdict(bundle, evidence_manifest=manifest)
    assert verdict["verdict"] == "NOT_PROVEN"
    assert "golden_result.json" in verdict["missing_identity"]


def test_bypass_bundle_hash_tampered_not_proven():
    from QCFP_MTF.governance.pure_release_judge import (
        issue_release_verdict,
    )
    bundle = _passing_bundle()
    manifest = _manifest_for(bundle)
    manifest["artifacts"] = manifest["artifacts"][:-1]
    verdict = issue_release_verdict(bundle, evidence_manifest=manifest)
    assert verdict["verdict"] == "NOT_PROVEN"


def test_bypass_mixed_release_evidence_rejected():
    from QCFP_MTF.governance.pure_release_judge import (
        issue_release_verdict,
    )
    bundle = _passing_bundle()
    bundle["golden_result.json"]["release_id"] = "REL-A"
    bundle["replay_result.json"]["release_id"] = "REL-B"
    manifest = _manifest_for(bundle)
    verdict = issue_release_verdict(bundle, evidence_manifest=manifest)
    assert verdict["verdict"] == "REJECTED"


# ------------------------- SF-5：Promotion Identity -----------------------

def test_bypass_old_release_qualification_blocked():
    from QCFP_MTF.governance.qualification_promotion import (
        promotion_verdict,
    )
    old = dict(_release_verdict_artifact(), release_id="REL-OLD")
    verdict = promotion_verdict("DEVELOPMENT", "SOFTWARE_QUALIFIED",
                                old, _promotion_context())
    assert verdict["verdict"] == "PROMOTION_BLOCKED"


def test_bypass_ai_human_approval_blocked():
    from QCFP_MTF.governance.qualification_promotion import (
        promotion_verdict,
    )
    evidence = _promotion_evidence()
    ai = _human_approval_artifact(evidence, actor_type="AI")
    verdict = promotion_verdict(
        "PRODUCTION_ELIGIBLE", "HUMAN_APPROVED",
        {"human_approval": ai, **evidence}, _promotion_context())
    assert verdict["verdict"] == "PROMOTION_BLOCKED"


def test_bypass_approval_hash_mismatch_blocked():
    from QCFP_MTF.governance.qualification_promotion import (
        promotion_verdict,
    )
    evidence = _promotion_evidence()
    approval = _human_approval_artifact(evidence)
    approval["release_verdict_hash"] = "wrong"
    verdict = promotion_verdict(
        "PRODUCTION_ELIGIBLE", "HUMAN_APPROVED",
        {"human_approval": approval, **evidence}, _promotion_context())
    assert verdict["verdict"] == "PROMOTION_BLOCKED"


# ------------------------- P1：Decision Delta Mandatory -------------------

def test_bypass_missing_decision_delta_gap():
    from QCFP_MTF.governance.acceptance_contract import acceptance_gate
    contract = _acceptance_contract()
    results = _acceptance_results()
    del results["decision_deltas"]
    gate = acceptance_gate(contract, results)
    assert gate["verdict"] == "EVIDENCE_GAP"


def test_bypass_builder_modifies_frozen_expected_rejected():
    from QCFP_MTF.governance.acceptance_contract import acceptance_gate
    results = _acceptance_results()
    results["positive_cases"][0]["expected_hash"] = "MUTATED"
    gate = acceptance_gate(_acceptance_contract(), results)
    assert gate["verdict"] == "ACCEPTANCE_FAIL"


# ------------------------- 历史攻击面（C1-C7 保留） ------------------------

def test_bypass_contract_without_change_impact_blocked():
    from QCFP_MTF.governance.implementation_contract import (
        bind_change_impact,
    )
    assert not bind_change_impact(_contract_base(), {})["bound"]


def test_bypass_manual_judge_tier_downgrade_rejected():
    from QCFP_MTF.governance.pure_release_judge import (
        issue_release_verdict,
    )
    bundle = _passing_bundle(tier="HIGH")
    manifest = _manifest_for(bundle)
    verdict = issue_release_verdict(
        bundle, change_tier="STANDARD", evidence_manifest=manifest)
    assert verdict["verdict"] == "REJECTED"


def test_bypass_empty_test_index_not_proven():
    from QCFP_MTF.governance.traceability import audit_traceability
    assert audit_traceability(tests_index=[])["verdict"] == \
        "TRACEABILITY_NOT_PROVEN"


def test_bypass_active_capability_without_traceability_rejected():
    from QCFP_MTF.governance.traceability import audit_traceability
    audit = audit_traceability(
        tests_index=["test_real"],
        production_features=["unmapped_active"])
    assert audit["verdict"] == "TRACEABILITY_FAIL"
    bundle = _passing_bundle()
    bundle["traceability.json"]["active_orphan_capabilities"] = \
        ["unmapped_active"]
    from QCFP_MTF.governance.pure_release_judge import (
        issue_release_verdict,
    )
    verdict = issue_release_verdict(
        bundle, evidence_manifest=_manifest_for(bundle))
    assert verdict["verdict"] == "REJECTED"


def test_bypass_open_critical_review_rejected():
    from QCFP_MTF.governance.evidence_aware_review import (
        resolve_review, review_gate,
    )
    report = {"change_id": "B-12", "findings": [
        {"finding_id": "REV-CRIT", "severity": "CRITICAL",
         "category": "SPEC_VIOLATION"}]}
    assert review_gate(resolve_review(report, {}))["verdict"] == "REJECTED"
    bundle = _passing_bundle()
    bundle["review_resolution.json"]["open_critical"] = 1
    from QCFP_MTF.governance.pure_release_judge import (
        issue_release_verdict,
    )
    assert issue_release_verdict(
        bundle, evidence_manifest=_manifest_for(bundle))["verdict"] == \
        "REJECTED"


def test_bypass_non_adjacent_promotion_jumps_blocked():
    from QCFP_MTF.governance.qualification_promotion import (
        promotion_verdict,
    )
    for jump in (("DEVELOPMENT", "SHADOW"),
                 ("DEVELOPMENT", "PRODUCTION_DSS"),
                 ("SOFTWARE_QUALIFIED", "PRODUCTION_ELIGIBLE"),
                 ("SHADOW", "PRODUCTION_DSS")):
        assert promotion_verdict(*jump)["verdict"] == "PROMOTION_BLOCKED"


def test_bypass_fake_boolean_qualification_blocked():
    from QCFP_MTF.governance.qualification_promotion import (
        promotion_verdict,
    )
    fake = {k: True for k in ("canonical_spec", "golden", "unit",
                              "integration", "invariant",
                              "replay_determinism")}
    assert promotion_verdict(
        "DEVELOPMENT", "SOFTWARE_QUALIFIED", fake,
        _promotion_context())["verdict"] == "PROMOTION_BLOCKED"


def test_bypass_missing_required_evidence_not_proven():
    from QCFP_MTF.governance.pure_release_judge import (
        issue_release_verdict,
    )
    bundle = _passing_bundle()
    manifest = _manifest_for(bundle)
    del bundle["scope_audit.json"]
    verdict = issue_release_verdict(bundle, evidence_manifest=manifest)
    assert verdict["verdict"] == "NOT_PROVEN"
    assert "scope_audit.json" in verdict["missing_artifacts"]


# ------------------------- 顶层证明测试 ------------------------------------

def _all_known_bypass_attempts_to_qualified():
    """组合所有已知攻击面，逐一断言无法 SOFTWARE_QUALIFIED。"""
    from QCFP_MTF.governance.pure_release_judge import (
        issue_release_verdict,
    )
    from QCFP_MTF.governance.patch_scope_lock import audit_patch_scope
    from QCFP_MTF.governance.change_impact_classification import (
        effective_change_impact,
    )
    # 1) 无 diff 的 impact
    impact = effective_change_impact(
        {"change_id": "B-90", "change_type": "docs",
         "description": "x", "touches": ["Research-only"]}, None)
    assert impact["status"] == "CHANGE_IMPACT_NOT_PROVEN"
    # 2) 空 patch evidence
    scope = audit_patch_scope(_patch_contract(), {},
                              _graph_before(), _graph_after(),
                              feature_manifest_after=_manifest_after())
    assert scope["verdict"] == "PATCH_NOT_PROVEN"
    # 3) 无 manifest 的 judge
    assert issue_release_verdict(_passing_bundle())["verdict"] == "NOT_PROVEN"
    # 4) 部分 identity
    bundle = _passing_bundle()
    manifest = _manifest_for(bundle)
    del bundle["golden_result.json"]["baseline_id"]
    assert issue_release_verdict(
        bundle, evidence_manifest=manifest)["verdict"] == "NOT_PROVEN"
    # 5) 混合 release
    bundle = _passing_bundle()
    bundle["replay_result.json"]["release_id"] = "REL-OTHER"
    manifest = _manifest_for(bundle)
    assert issue_release_verdict(
        bundle, evidence_manifest=manifest)["verdict"] == "REJECTED"
    # 6) 恶意枚举
    bundle = _passing_bundle()
    bundle["pit_result.json"]["status"] = "UNQUALIFIED"
    assert issue_release_verdict(
        bundle, evidence_manifest=_manifest_for(bundle))["verdict"] == \
        "NOT_PROVEN"


def _all_known_bypass_attempts_to_production_dss():
    from QCFP_MTF.governance.qualification_promotion import (
        promotion_verdict,
    )
    # 1) 跳级
    assert promotion_verdict("DEVELOPMENT", "PRODUCTION_DSS")["verdict"] == \
        "PROMOTION_BLOCKED"
    assert promotion_verdict("SHADOW", "PRODUCTION_DSS")["verdict"] == \
        "PROMOTION_BLOCKED"
    # 2) AI approval
    evidence = _promotion_evidence()
    ai = _human_approval_artifact(evidence, actor_type="AI")
    assert promotion_verdict(
        "PRODUCTION_ELIGIBLE", "HUMAN_APPROVED",
        {"human_approval": ai, **evidence},
        _promotion_context())["verdict"] == "PROMOTION_BLOCKED"
    # 3) 旧 release approval
    evidence = _promotion_evidence()
    old = _human_approval_artifact(evidence)
    old["release_id"] = "REL-OLD"
    assert promotion_verdict(
        "PRODUCTION_ELIGIBLE", "HUMAN_APPROVED",
        {"human_approval": old, **evidence},
        _promotion_context())["verdict"] == "PROMOTION_BLOCKED"
    # 4) fake boolean
    fake = {k: True for k in ("canonical_spec", "golden")}
    assert promotion_verdict(
        "DEVELOPMENT", "SOFTWARE_QUALIFIED", fake,
        _promotion_context())["verdict"] == "PROMOTION_BLOCKED"


def test_no_bypass_path_to_software_qualified():
    _all_known_bypass_attempts_to_qualified()


def test_no_bypass_path_to_production_dss():
    _all_known_bypass_attempts_to_production_dss()
