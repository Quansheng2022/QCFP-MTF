# coding: utf-8
"""流程治理工程（Flow Governance Engineering）单测：
    Sprint A（1-3）+ FGC-1 C1-C7 + FGC-1 Surgical Fix Pack（SF-1~SF-5 + P1）
"""

import hashlib
import json
import tempfile
from pathlib import Path


def _tmp_dir():
    return tempfile.TemporaryDirectory()


def _contract_base() -> dict:
    return {
        "change_id": "CHG-TEST-001",
        "objective": "test",
        "spec_ids": ["QCFP-SPEC-CHG-002"],
        "change_type": "STANDARD",
        "change_impact_artifact": "change_impact.json",
        "change_impact_hash": "impact-hash",
        "change_tier": "STANDARD",
        "allowed_files": ["Core/QCFP_MTF/decision/engine.py"],
        "forbidden_files": ["Core/QCFP_MTF/decision/governance.py"],
        "authorities_touched": [],
        "expected_behavior_change": "x",
        "expected_unchanged_behavior": "y",
        "acceptance_criteria": ["golden unchanged"],
    }


def _diff_evidence(changed_files=None, source="abc", target="def",
                   diff_hash="diff-hash") -> dict:
    return {
        "schema": "OBSERVED-DIFF-2",
        "source_commit": source,
        "target_commit": target,
        "diff_hash": diff_hash,
        "changed_files": list(changed_files or []),
        "generator": "qcfp-diff-generator",
        "generator_version": "2",
    }


# ------------------------- Sprint A #1 Canonical Spec ---------------------

def test_spec_conformance_real_file():
    from QCFP_MTF.governance.canonical_spec import spec_conformance
    result = spec_conformance()
    assert result["conformant"], result
    assert result["verdict"] == "SPEC_CONFORMANT"
    assert result["schema"] == "SPEC-CONFORMANCE-2"


def test_spec_entries_have_stable_ids():
    from QCFP_MTF.governance.canonical_spec import spec_entries
    ids = [e["id"] for e in spec_entries()]
    assert len(ids) == len(set(ids))


def test_spec_forbids_implementation_detail():
    from QCFP_MTF.governance.canonical_spec import spec_conformance
    with _tmp_dir() as d:
        bad = Path(d) / "CANONICAL_SPEC.md"
        bad.write_text("# CS-00\n\n## CS-10\n\n```python\ndef x(): pass\n"
                       "```\n", encoding="utf-8")
        assert not spec_conformance(bad)["conformant"]


# ------------------------- Sprint A #2 Baseline Freeze --------------------

def test_baseline_compute_has_all_fields():
    from QCFP_MTF.governance.governance_baseline import compute_baseline
    b = compute_baseline()
    assert b["baseline_id"].startswith("GOV-BASELINE")
    for field in ("spec_hash", "architecture_hash",
                  "production_manifest_hash", "golden_corpus_hash",
                  "constitution_hash"):
        assert field in b


def test_baseline_hashes_cover_real_files():
    from QCFP_MTF.governance.governance_baseline import (
        architecture_hash, golden_corpus_hash, spec_hash,
    )
    empty = hashlib.sha256(b"").hexdigest()
    assert spec_hash() != empty
    assert architecture_hash() != empty
    assert golden_corpus_hash() != empty


def test_baseline_create_only_immutable():
    from QCFP_MTF.governance.governance_baseline import (
        compute_baseline, write_baseline,
    )
    with _tmp_dir() as d:
        out = Path(d)
        b = compute_baseline()
        assert write_baseline(b, out)["frozen"]
        assert not write_baseline(b, out)["frozen"]


def test_baseline_verify_detects_drift():
    from QCFP_MTF.governance.governance_baseline import (
        compute_baseline, verify_baseline,
    )
    b = compute_baseline()
    assert verify_baseline(dict(b))["verdict"] == "PASS"
    drifted = dict(b)
    drifted["spec_hash"] = "deadbeef"
    assert verify_baseline(drifted)["verdict"] == "BASELINE_CHANGED"


def test_baseline_candidate_requires_human_approval():
    from QCFP_MTF.governance.governance_baseline import (
        approve_baseline_candidate, compute_baseline,
        create_baseline_candidate, load_baseline,
        validate_baseline_candidate, write_baseline,
    )
    with _tmp_dir() as d:
        out = Path(d)
        frozen = compute_baseline()
        write_baseline(frozen, out)
        assert create_baseline_candidate(out)["created"]
        assert validate_baseline_candidate(out)["valid"]
        assert not approve_baseline_candidate(
            out, human_approved=False)["approved"]
        assert approve_baseline_candidate(
            out, human_approved=True)["approved"]
        new_frozen = load_baseline(out / "governance_baseline.json")
        assert new_frozen["baseline_id"] != frozen["baseline_id"]


def test_candidate_rejects_authority_surface_hash_tamper():
    """A13：篡改 Candidate 的 phase1_authority_surface_hash → CANDIDATE_INVALID。"""
    from QCFP_MTF.governance.governance_baseline import (
        compute_baseline, create_baseline_candidate,
        validate_baseline_candidate, write_baseline,
    )
    with _tmp_dir() as d:
        out = Path(d)
        write_baseline(compute_baseline(), out)
        assert create_baseline_candidate(out)["created"]
        candidate_path = out / "governance_baseline_candidate.json"
        candidate = json.loads(
            candidate_path.read_text(encoding="utf-8"))
        candidate["phase1_authority_surface_hash"] = "deadbeef"
        candidate_path.write_text(
            json.dumps(candidate, ensure_ascii=False),
            encoding="utf-8")
        result = validate_baseline_candidate(out)
        assert not result["valid"]
        assert result["verdict"] == "CANDIDATE_INVALID"
        assert "phase1_authority_surface_hash" \
            in result["recompute_inconsistent"]


def test_approval_rejects_invalid_authority_surface_candidate():
    """A14：human_approved=True 也不能批准被篡改的 Candidate，Frozen 不被替换。"""
    from QCFP_MTF.governance.governance_baseline import (
        approve_baseline_candidate, compute_baseline,
        create_baseline_candidate, write_baseline,
    )
    with _tmp_dir() as d:
        out = Path(d)
        frozen = compute_baseline()
        write_baseline(frozen, out)
        assert create_baseline_candidate(out)["created"]
        candidate_path = out / "governance_baseline_candidate.json"
        candidate = json.loads(
            candidate_path.read_text(encoding="utf-8"))
        candidate["phase1_authority_surface_hash"] = "deadbeef"
        candidate_path.write_text(
            json.dumps(candidate, ensure_ascii=False),
            encoding="utf-8")
        result = approve_baseline_candidate(out, human_approved=True)
        assert not result["approved"]
        frozen_path = out / "governance_baseline.json"
        assert frozen_path.exists()
        frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
        assert frozen["phase1_authority_surface_hash"] != "deadbeef"
        assert (out / "governance_baseline_candidate.json").exists()


def test_candidate_authority_surface_hash_valid_passes():
    """正向：正常 Candidate 的 authority surface hash 与重算一致 → CANDIDATE_VALID。"""
    from QCFP_MTF.governance.governance_baseline import (
        compute_baseline, create_baseline_candidate,
        validate_baseline_candidate, write_baseline,
    )
    with _tmp_dir() as d:
        out = Path(d)
        write_baseline(compute_baseline(), out)
        assert create_baseline_candidate(out)["created"]
        result = validate_baseline_candidate(out)
        assert result["valid"]
        assert result["verdict"] == "CANDIDATE_VALID"
        assert "phase1_authority_surface_hash" \
            not in result["recompute_inconsistent"]


# ------------------ Sprint A #3 Traceability（FGC-1 C1） -------------------

def test_traceability_manifest_real_audit():
    from QCFP_MTF.governance.traceability import audit_traceability
    result = audit_traceability()
    assert result["verdict"] == "TRACEABILITY_PASS", result
    assert result["schema"] == "TRACEABILITY-2"
    assert result["test_index_status"] == "VALID"
    assert result["test_count"] > 0
    assert result["p0_fully_connected"] == result["p0_total"]
    assert not result["active_orphan_capabilities"]


def test_traceability_empty_test_index_not_proven():
    from QCFP_MTF.governance.traceability import audit_traceability
    result = audit_traceability(tests_index=[])
    assert result["verdict"] == "TRACEABILITY_NOT_PROVEN"


def test_traceability_orphan_requirement_error():
    from QCFP_MTF.governance.traceability import audit_traceability
    manifest = [{
        "spec_id": "QCFP-SPEC-TEST-001", "requirement": "no test",
        "architecture_rule": [], "authority": "",
        "production_modules": [], "tests": [],
        "failure_injection": [], "evidence": [], "release_gate": [],
    }]
    result = audit_traceability(manifest, tests_index=["test_real"])
    assert result["verdict"] == "TRACEABILITY_FAIL"


def test_traceability_active_orphan_capability_fail():
    from QCFP_MTF.governance.traceability import audit_traceability
    result = audit_traceability(
        tests_index=["test_real"],
        production_features=["unmapped_feature"])
    assert "unmapped_feature" in result["active_orphan_capabilities"]
    assert result["verdict"] == "TRACEABILITY_FAIL"


# --------------------- Sprint B #4 Implementation Contract ----------------

def test_implementation_contract_scope_violation():
    from QCFP_MTF.governance.implementation_contract import (
        check_change_surface,
    )
    result = check_change_surface(
        _contract_base(),
        ["Core/QCFP_MTF/decision/engine.py",
         "Core/QCFP_MTF/decision/unknown.py",
         "Core/QCFP_MTF/decision/governance.py"])
    assert result["verdict"] == "SCOPE_VIOLATION"
    kinds = {v["kind"] for v in result["violations"]}
    assert "FILE_SCOPE" in kinds and "PROTECTED_SURFACE" in kinds


def test_implementation_contract_ok_within_surface():
    from QCFP_MTF.governance.implementation_contract import (
        check_change_surface,
    )
    result = check_change_surface(
        _contract_base(), ["Core/QCFP_MTF/decision/engine.py"])
    assert result["verdict"] == "CONTRACT_OK"


def test_implementation_contract_binds_change_impact():
    from QCFP_MTF.governance.implementation_contract import (
        bind_change_impact,
    )
    impact = {"schema": "CHANGE-IMPACT-2", "change_id": "CHG-TEST-001",
              "change_hash": "impact-hash", "tier": "STANDARD",
              "approved_for_contract": True}
    assert bind_change_impact(_contract_base(), impact)["bound"]
    assert not bind_change_impact(
        _contract_base(), dict(impact, change_id="OTHER"))["bound"]
    assert not bind_change_impact(
        _contract_base(), dict(impact, change_hash="wrong"))["bound"]
    assert not bind_change_impact(
        _contract_base(), dict(impact, tier="HIGH"))["bound"]
    assert not bind_change_impact(_contract_base(), {})["bound"]


# ---------------- Sprint B #5 Acceptance Contract（C3 + P1） ----------------

def _acceptance_contract() -> dict:
    return {
        "change_id": "CHG-TEST-001",
        "change_tier": "STANDARD",
        "spec_requirements": ["QCFP-SPEC-INV-001"],
        "positive_cases": [{
            "case_id": "POS-001", "spec_ids": ["QCFP-SPEC-AUTH-001"],
            "input_fixture": {"fixture_id": "FIX-PERM-001",
                              "input_hash": "abc"},
            "expected": {"permission": "WATCH", "result_hash": "xyz"},
        }],
        "boundary_cases": [],
        "negative_cases": [{
            "case_id": "NEG-001", "spec_ids": ["QCFP-SPEC-INV-001"],
            "input_fixture": {"fixture_id": "FIX-PERM-002",
                              "input_hash": "abc2"},
            "expected": {"result_hash": "xyz2"},
        }],
        "adversarial_cases": [],
        "golden_cases": [],
        "frozen_golden_expected": True,
        "expected_invariant_results": [],
        "expected_decision_deltas": {"max_changed_decisions": 12,
                                     "allowed_fields": [],
                                     "forbidden_fields":
                                         ["institutional_permission",
                                          "final_target"],
                                     "expected_direction": {}},
        "expected_unchanged_cases": [],
        "test_oracle_change": {"required": False},
    }


def _acceptance_results() -> dict:
    return {
        "positive_cases": [{
            "case_id": "POS-001", "input_hash": "abc",
            "expected_hash": "xyz", "actual_hash": "xyz", "pass": True}],
        "negative_cases": [{
            "case_id": "NEG-001", "input_hash": "abc2",
            "expected_hash": "xyz2", "actual_hash": "xyz2", "pass": True}],
        "golden": {"n_total": 3, "n_failed": 0, "status": "PASS"},
        "invariants": [True],
        "unchanged": [True],
        "decision_deltas": {"changed_decisions": 3,
                            "changed_fields": ["binding_constraint"],
                            "direction_checks": {}},
    }


def test_acceptance_contract_critical_requires_four_case_kinds():
    from QCFP_MTF.governance.acceptance_contract import (
        validate_acceptance_contract,
    )
    contract = _acceptance_contract()
    result = validate_acceptance_contract(contract, critical_change=True)
    assert not result["valid"]
    assert any("boundary_cases" in e for e in result["errors"])


def test_acceptance_gate_pass_fail_and_gap():
    from QCFP_MTF.governance.acceptance_contract import (
        acceptance_gate, validate_acceptance_contract,
    )
    contract = _acceptance_contract()
    assert validate_acceptance_contract(contract)["valid"]
    assert acceptance_gate(contract, _acceptance_results())["verdict"] == \
        "ACCEPTANCE_PASS"
    failing = _acceptance_results()
    failing["positive_cases"][0]["actual_hash"] = "WRONG"
    assert acceptance_gate(contract, failing)["verdict"] == "ACCEPTANCE_FAIL"
    gap = _acceptance_results()
    del gap["golden"]
    assert acceptance_gate(contract, gap)["verdict"] == "EVIDENCE_GAP"


def test_acceptance_decision_delta_missing_is_gap():
    """P1：expected_decision_deltas 已配置 → actual decision_deltas 必填。"""
    from QCFP_MTF.governance.acceptance_contract import acceptance_gate
    contract = _acceptance_contract()
    results = _acceptance_results()
    del results["decision_deltas"]
    gate = acceptance_gate(contract, results)
    assert gate["verdict"] == "EVIDENCE_GAP"
    assert any("changed_decisions" in g for g in gate["evidence_gaps"])


def test_acceptance_decision_delta_too_large_fail():
    from QCFP_MTF.governance.acceptance_contract import acceptance_gate
    results = _acceptance_results()
    results["decision_deltas"] = {
        "changed_decisions": 30,
        "changed_fields": ["binding_constraint"],
        "direction_checks": {}}
    gate = acceptance_gate(_acceptance_contract(), results)
    assert gate["verdict"] == "ACCEPTANCE_FAIL"


def test_acceptance_oracle_change_requires_full_audit_fields():
    from QCFP_MTF.governance.acceptance_contract import (
        validate_acceptance_contract,
    )
    contract = _acceptance_contract()
    contract["test_oracle_change"] = {
        "required": True, "oracle_change_adr_hash": "",
        "human_approval_id": "", "previous_oracle_hash": "",
        "new_oracle_hash": "", "reason": ""}
    result = validate_acceptance_contract(contract)
    assert not result["valid"]
    assert any("oracle_change_adr_hash" in e for e in result["errors"])


# ------------------ Sprint B #6 Change Impact（SF-1） ----------------------

def test_change_impact_high_for_critical_areas():
    from QCFP_MTF.governance.change_impact_classification import (
        classify_change,
    )
    impact = classify_change({
        "change_id": "C4", "change_type": "modify",
        "description": "permission change", "touches": ["Permission"]})
    assert impact["tier"] == "HIGH"


def test_change_impact_requires_observed_diff():
    from QCFP_MTF.governance.change_impact_classification import (
        effective_change_impact,
    )
    change = {"change_id": "C5", "change_type": "docs",
              "description": "LOW", "touches": ["Research-only"]}
    impact = effective_change_impact(change, None)
    assert impact["status"] == "CHANGE_IMPACT_NOT_PROVEN"
    assert impact["approved_for_contract"] is False


def test_change_impact_observed_diff_schema_required():
    from QCFP_MTF.governance.change_impact_classification import (
        effective_change_impact,
    )
    change = {"change_id": "C5", "change_type": "docs",
              "description": "x", "touches": ["Research-only"]}
    bad = _diff_evidence()
    del bad["schema"]
    assert effective_change_impact(change, bad)["status"] == \
        "CHANGE_IMPACT_NOT_PROVEN"
    no_hash = _diff_evidence()
    del no_hash["diff_hash"]
    assert effective_change_impact(change, no_hash)["status"] == \
        "CHANGE_IMPACT_NOT_PROVEN"


def test_change_impact_empty_diff_semantics():
    from QCFP_MTF.governance.change_impact_classification import (
        effective_change_impact,
    )
    change = {"change_id": "C5", "change_type": "docs",
              "description": "x", "touches": ["Research-only"]}
    no_change = effective_change_impact(
        change, _diff_evidence([], source="abc", target="abc"))
    assert no_change["status"] == "CHANGE_IMPACT_NO_CHANGE"
    empty_mismatch = effective_change_impact(
        change, _diff_evidence([], source="abc", target="def"))
    assert empty_mismatch["status"] == "CHANGE_IMPACT_NOT_PROVEN"


def test_change_impact_observed_diff_upgrades_tier():
    from QCFP_MTF.governance.change_impact_classification import (
        effective_change_impact,
    )
    change = {"change_id": "C6", "change_type": "docs",
              "description": "declared LOW", "touches": ["Research-only"]}
    effective = effective_change_impact(
        change, _diff_evidence(
            ["Core/QCFP_MTF/decision/institutional_permission.py"]))
    assert effective["tier"] == "HIGH"
    assert effective["declared_tier"] == "LOW"
    assert effective["observed_tier"] == "HIGH"
    assert effective["status"] == "CHANGE_IMPACT_READY"
    assert effective["approved_for_contract"] is True


def test_change_impact_approved_computed_not_declared():
    from QCFP_MTF.governance.change_impact_classification import (
        change_impact_record,
    )
    change = {"change_id": "", "change_type": "docs",
              "description": "x", "touches": ["Research-only"],
              "approved_for_contract": True}
    record = change_impact_record(change, _diff_evidence(["README.md"]))
    assert record["impact"]["approved_for_contract"] is False


# --------------------- Sprint C #7 Evidence-Aware Review ------------------

def test_review_requires_all_fixed_inputs():
    from QCFP_MTF.governance.evidence_aware_review import review_report
    assert review_report({"inputs": {}})["verdict"] == "REVIEW_NOT_STARTED"


def test_review_clean_allowed_release_pass_forbidden():
    from QCFP_MTF.governance.evidence_aware_review import review_report
    inputs = {
        "change_id": "C7", "spec_ids": ["QCFP-SPEC-INV-001"],
        "architecture_baseline": "x", "implementation_contract": "x",
        "actual_diff": "x", "test_evidence": "x", "authority_audit": "x",
        "complexity_diff": "x", "changed_decision_samples": "x",
        "known_not_proven_items": [],
    }
    clean = review_report({"change_id": "C7", "inputs": inputs,
                           "findings": [{
                               "finding_id": "F-1", "severity": "MINOR",
                               "category": "NO_ISSUE", "spec_id": "",
                               "evidence": "", "affected_file": "",
                               "why": "", "required_correction": "",
                               "acceptance_condition": ""}]})
    assert clean["verdict"] == "REVIEW_CLEAN"
    assert clean["schema"] == "REVIEW-2"
    invalid = review_report({"change_id": "C7", "inputs": inputs,
                             "findings": [{
                                 "finding_id": "F-2", "severity": "MAJOR",
                                 "category": "RELEASE_PASS",
                                 "spec_id": "", "evidence": "",
                                 "affected_file": "", "why": "",
                                 "required_correction": "",
                                 "acceptance_condition": ""}]})
    assert invalid["verdict"] == "REVIEW_INVALID"


def test_review_resolution_gate_blocks_open_critical():
    from QCFP_MTF.governance.evidence_aware_review import (
        resolve_review, review_gate,
    )
    report = {"change_id": "C8", "findings": [
        {"finding_id": "REV-1", "severity": "CRITICAL",
         "category": "SPEC_VIOLATION"}]}
    assert review_gate(resolve_review(report, {}))["verdict"] == "REJECTED"
    fixed = resolve_review(report, {"REV-1": {
        "resolution": "FIXED", "patch_id": "P-1",
        "verification_test": "test_x", "verified": True}})
    assert review_gate(fixed)["verdict"] == "REVIEW_RESOLVED"


# --------------------- Sprint C #8 Patch Scope Lock（C4 + SF-2） -----------

def _patch_contract() -> dict:
    from QCFP_MTF.governance.patch_scope_lock import patch_contract_template
    contract = patch_contract_template()
    contract["change_id"] = "CHG-TEST-001"
    contract["implementation_contract_hash"] = "contract-hash"
    contract["allowed_files"] = [
        "Core/QCFP_MTF/decision/engine.py"]
    contract["allowed_functions"] = ["decision.engine.evaluate"]
    return contract


def _patch_evidence(changed_files=None, changed_functions=None,
                    import_delta=None, schema_hashes=None,
                    golden=(0, []), newly_active=None) -> dict:
    schema_hashes = schema_hashes or ("same", "same")
    return {
        "schema": "PATCH-EVIDENCE-2",
        "change_id": "CHG-TEST-001",
        "source_commit": "abc", "target_commit": "def",
        "diff_hash": "patch-diff-hash",
        "changed_files": list(changed_files or []),
        "changed_functions": list(changed_functions or []),
        "import_delta": list(import_delta or []),
        "schema_delta": {
            "changed": bool(schema_hashes and schema_hashes[0] !=
                            schema_hashes[1]),
            "hash_before": (schema_hashes or (None, None))[0],
            "hash_after": (schema_hashes or (None, None))[1],
        },
        "feature_delta": {"newly_active": list(newly_active or [])},
        "golden_delta": {"changed_count": golden[0],
                         "changed_fields": list(golden[1])},
        "generator": "qcfp-diff-generator",
        "generator_version": "2",
    }


def _graph_before():
    return {"nodes": {"decision.engine": {"authority": "NONE"}},
            "roots": {"r": "QCFP_MTF.decision.engine.evaluate"}}


def _graph_after(new_authority=None):
    nodes = {"decision.engine": {"authority": "NONE"}}
    if new_authority:
        nodes[new_authority] = {"authority": "FINAL_TARGET"}
    return {"nodes": nodes,
            "roots": {"r": "QCFP_MTF.decision.engine.evaluate"}}


def _manifest_after(extra_active=None):
    from QCFP_MTF.governance.minimal_trusted_release import \
        FROZEN_PRODUCTION_MANIFEST
    m = {f: dict(i) for f, i in FROZEN_PRODUCTION_MANIFEST.items()}
    for f in (extra_active or []):
        m[f] = {"state": "ACTIVE", "owner": "decision.secret"}
    return m


def test_patch_scope_not_proven_without_evidence():
    from QCFP_MTF.governance.patch_scope_lock import audit_patch_scope
    result = audit_patch_scope(_patch_contract(), None,
                               _graph_before(), _graph_after())
    assert result["verdict"] == "PATCH_NOT_PROVEN"
    assert "patch_evidence" in result["missing_evidence"]


def test_patch_scope_not_proven_without_graphs():
    from QCFP_MTF.governance.patch_scope_lock import audit_patch_scope
    result = audit_patch_scope(
        _patch_contract(), _patch_evidence(
            ["Core/QCFP_MTF/decision/engine.py"]),
        None, None, feature_manifest_after=_manifest_after())
    assert result["verdict"] == "PATCH_NOT_PROVEN"
    assert "authority_graph_before" in result["missing_evidence"]
    assert "authority_graph_after" in result["missing_evidence"]


def test_patch_scope_file_and_function_violation():
    from QCFP_MTF.governance.patch_scope_lock import audit_patch_scope
    result = audit_patch_scope(
        _patch_contract(),
        _patch_evidence(
            ["Core/QCFP_MTF/decision/engine.py",
             "Core/QCFP_MTF/decision/ledger.py"],
            changed_functions=["decision.engine.evaluate",
                               "decision.governance.evaluate"]),
        _graph_before(), _graph_after(),
        feature_manifest_after=_manifest_after())
    assert result["verdict"] == "PATCH_REJECTED"
    kinds = {v["kind"] for v in result["violations"]}
    assert "FILE_SCOPE" in kinds and "FUNCTION_SCOPE" in kinds


def test_patch_scope_forbidden_import():
    from QCFP_MTF.governance.patch_scope_lock import audit_patch_scope
    contract = _patch_contract()
    contract["forbidden_modules"] = ["research"]
    result = audit_patch_scope(
        contract,
        _patch_evidence(
            ["Core/QCFP_MTF/decision/engine.py"],
            import_delta=[{"target": "research.future_label"}]),
        _graph_before(), _graph_after(),
        feature_manifest_after=_manifest_after())
    assert result["verdict"] == "PATCH_REJECTED"
    assert any(v["kind"] == "FORBIDDEN_DEPENDENCY"
               for v in result["violations"])


def test_patch_scope_rejects_self_declared_expected():
    from QCFP_MTF.governance.patch_scope_lock import audit_patch_scope
    evidence = _patch_evidence(["Core/QCFP_MTF/decision/engine.py"])
    evidence["schema_delta"]["expected"] = True
    result = audit_patch_scope(
        _patch_contract(), evidence, _graph_before(), _graph_after(),
        feature_manifest_after=_manifest_after())
    assert result["verdict"] == "PATCH_REJECTED"
    assert any(v["kind"] == "SELF_DECLARED_EXPECTED"
               for v in result["violations"])


def test_patch_scope_schema_hash_mismatch_rejected():
    from QCFP_MTF.governance.patch_scope_lock import audit_patch_scope
    result = audit_patch_scope(
        _patch_contract(),
        _patch_evidence(
            ["Core/QCFP_MTF/decision/engine.py"],
            schema_hashes=("hash-before", "hash-after")),
        _graph_before(), _graph_after(),
        feature_manifest_after=_manifest_after())
    assert result["verdict"] == "PATCH_REJECTED"
    assert any(v["kind"] == "SCHEMA_SCOPE"
               for v in result["violations"])


def test_patch_scope_manifest_adds_active_feature_rejected():
    from QCFP_MTF.governance.patch_scope_lock import audit_patch_scope
    result = audit_patch_scope(
        _patch_contract(),
        _patch_evidence(["Core/QCFP_MTF/decision/engine.py"]),
        _graph_before(), _graph_after(),
        feature_manifest_after=_manifest_after(["secret_feature"]))
    assert result["verdict"] == "PATCH_REJECTED"
    assert any(v["kind"] == "FEATURE_SCOPE"
               for v in result["violations"])


def test_patch_scope_authority_writer_delta_rejected():
    from QCFP_MTF.governance.patch_scope_lock import audit_patch_scope
    before = {"nodes": {"decision.engine": {"authority": "NONE"}},
              "roots": {"r": "QCFP_MTF.decision.engine.evaluate"}}
    after = {"nodes": {
        "decision.engine": {"authority": "NONE"},
        "decision.governance": {"authority": "FINAL_TARGET",
                                "field_writers": ["final_target"]}},
        "roots": {"r": "QCFP_MTF.decision.engine.evaluate"}}
    result = audit_patch_scope(
        _patch_contract(),
        _patch_evidence(["Core/QCFP_MTF/decision/engine.py"]),
        before, after, feature_manifest_after=_manifest_after())
    assert result["verdict"] == "PATCH_REJECTED"
    assert result["authority_source"] == "AUTHORITY_GRAPH"
    assert any(v["kind"] == "AUTHORITY_WRITER_DELTA"
               for v in result["violations"])


def test_patch_scope_accepted_when_clean():
    from QCFP_MTF.governance.patch_scope_lock import audit_patch_scope
    result = audit_patch_scope(
        _patch_contract(),
        _patch_evidence(
            ["Core/QCFP_MTF/decision/engine.py"],
            changed_functions=["decision.engine.evaluate"],
            schema_hashes=("same", "same")),
        _graph_before(), _graph_after(),
        feature_manifest_after=_manifest_after())
    assert result["verdict"] == "PATCH_ACCEPTED"
    assert result["authority_source"] == "AUTHORITY_GRAPH"


# --------------------- Sprint D #9 Pure Release Judge（C5/C7/SF-3/SF-4） ---

def _artifact(name, schema, extra=None, **identity):
    data = {"schema": schema, "change_id": "CHG-TEST-001",
            "baseline_id": "GOV-BASELINE-3", "release_id": "REL-1"}
    data.update(identity)
    if extra:
        data.update(extra)
    return data


def _passing_bundle(tier="STANDARD"):
    bundle = {
        "change_impact.json": _artifact(
            "change_impact.json", "CHANGE-IMPACT-2",
            {"change_hash": "h", "tier": tier,
             "approved_for_contract": True}),
        "baseline.json": _artifact(
            "baseline.json", "BASELINE-GATE-2",
            {"verdict": "BASELINE_PASS", "pass": True}),
        "spec_conformance.json": _artifact(
            "spec_conformance.json", "SPEC-CONFORMANCE-2",
            {"verdict": "SPEC_CONFORMANT", "conformant": True,
             "pass": True}),
        "architecture_conformance.json": _artifact(
            "architecture_conformance.json", "ARCHITECTURE-CONFORMANCE-2",
            {"verdict": "ARCHITECTURE_PASS", "pass": True}),
        "implementation_contract_result.json": _artifact(
            "implementation_contract_result.json", "CONTRACT-RESULT-2",
            {"verdict": "CONTRACT_OK", "pass": True}),
        "acceptance_result.json": _artifact(
            "acceptance_result.json", "ACCEPTANCE-RESULT-2",
            {"verdict": "ACCEPTANCE_PASS", "pass": True}),
        "traceability.json": _artifact(
            "traceability.json", "TRACEABILITY-2",
            {"verdict": "TRACEABILITY_PASS", "test_index_status": "VALID",
             "active_orphan_capabilities": [], "pass": True}),
        "scope_audit.json": _artifact(
            "scope_audit.json", "SCOPE-2",
            {"violations": [], "verdict": "PATCH_ACCEPTED"}),
        "authority_graph.json": _artifact(
            "authority_graph.json", "AUTHORITY-GRAPH-2",
            {"verdict": "AUTHORITY_OK"}),
        "review_report.json": _artifact(
            "review_report.json", "REVIEW-2",
            {"verdict": "REVIEW_CLEAN", "certification_authority": "None"}),
        "review_resolution.json": _artifact(
            "review_resolution.json", "REVIEW-RESOLUTION-2",
            {"open_critical": 0, "open_major": 0,
             "gate": {"verdict": "REVIEW_RESOLVED"}}),
        "golden_result.json": _artifact(
            "golden_result.json", "GOLDEN-2",
            {"status": "PASS", "n_total": 3, "n_failed": 0,
             "critical_failures": 0}),
        "invariant_result.json": _artifact(
            "invariant_result.json", "INVARIANT-2",
            {"status": "PASS", "failures": []}),
        "replay_result.json": _artifact(
            "replay_result.json", "REPLAY-2",
            {"n_current_release": 5, "eligible_rate": 1.0,
             "exact_rate": 1.0, "critical_mismatch": 0}),
        "pit_result.json": _artifact(
            "pit_result.json", "PIT-2", {"status": "PASS"}),
        "failure_injection_result.json": _artifact(
            "failure_injection_result.json", "FAILURE-INJECTION-2",
            {"status": "PASS", "failure_escaped_count": 0}),
        "complexity_diff.json": _artifact(
            "complexity_diff.json", "COMPLEXITY-2",
            {"verdict": "WITHIN_BUDGET", "pass": True}),
        "test_summary.json": _artifact(
            "test_summary.json", "TEST-SUMMARY-2",
            {"status": "PASS", "n_failed": 0}),
    }
    if tier == "HIGH":
        bundle.update({
            "oos_result.json": _artifact(
                "oos_result.json", "OOS-2",
                {"status": "OOS_PASS", "comparable": True,
                 "evidence_not_down": True}),
            "ablation_result.json": _artifact(
                "ablation_result.json", "ABLATION-2",
                {"verdict": "INCREMENTAL_ALPHA", "pass": True}),
            "stress_result.json": _artifact(
                "stress_result.json", "STRESS-2",
                {"survivable": True}),
            "shadow_result.json": _artifact(
                "shadow_result.json", "SHADOW-2",
                {"status": "PASS"}),
        })
    return bundle


def _manifest_for(bundle, change_id="CHG-TEST-001", release_id="REL-1",
                  baseline_id="GOV-BASELINE-3") -> dict:
    from QCFP_MTF.governance.pure_release_judge import make_evidence_manifest
    return make_evidence_manifest(
        bundle, change_id, release_id, baseline_id)["manifest"]


def test_judge_requires_manifest_not_proven():
    from QCFP_MTF.governance.pure_release_judge import (
        issue_release_verdict,
    )
    verdict = issue_release_verdict(_passing_bundle())
    assert verdict["verdict"] == "NOT_PROVEN"
    assert "evidence_manifest" in verdict["reason"]


def test_judge_qualified_when_all_pass():
    from QCFP_MTF.governance.pure_release_judge import (
        issue_release_verdict,
    )
    bundle = _passing_bundle()
    verdict = issue_release_verdict(
        bundle, evidence_manifest=_manifest_for(bundle))
    assert verdict["verdict"] == "SOFTWARE_QUALIFIED", verdict


def test_judge_rejected_on_explicit_failure():
    from QCFP_MTF.governance.pure_release_judge import (
        issue_release_verdict,
    )
    bundle = _passing_bundle()
    bundle["golden_result.json"]["status"] = "FAIL"
    verdict = issue_release_verdict(
        bundle, evidence_manifest=_manifest_for(bundle))
    assert verdict["verdict"] == "REJECTED"
    assert "golden_result.json" in verdict["failed_artifacts"]


def test_judge_not_proven_on_indeterminate():
    from QCFP_MTF.governance.pure_release_judge import (
        issue_release_verdict,
    )
    bundle = _passing_bundle()
    bundle["test_summary.json"] = _artifact(
        "test_summary.json", "TEST-SUMMARY-2",
        {"status": "MAYBE", "n_failed": 0})
    verdict = issue_release_verdict(
        bundle, evidence_manifest=_manifest_for(bundle))
    assert verdict["verdict"] == "NOT_PROVEN"
    assert "test_summary.json" in verdict["indeterminate_artifacts"]


def test_judge_high_requires_extra_artifacts():
    from QCFP_MTF.governance.pure_release_judge import (
        issue_release_verdict,
    )
    bundle = _passing_bundle(tier="HIGH")
    manifest = _manifest_for(bundle)
    del bundle["oos_result.json"]
    verdict = issue_release_verdict(
        bundle, evidence_manifest=manifest)
    assert verdict["verdict"] == "NOT_PROVEN"
    assert "oos_result.json" in verdict["missing_artifacts"]


def test_judge_malicious_enums_are_not_proven():
    from QCFP_MTF.governance.pure_release_judge import (
        issue_release_verdict,
    )
    for bad in ("NOT_VALIDATED", "UNQUALIFIED", "NOT_OK", "PASSING",
                "VALIDATION_FAIL", "MAYBE", "UNKNOWN"):
        bundle = _passing_bundle()
        bundle["pit_result.json"]["status"] = bad
        verdict = issue_release_verdict(
            bundle, evidence_manifest=_manifest_for(bundle))
        assert verdict["verdict"] == "NOT_PROVEN", (bad, verdict)


def test_judge_mixed_release_artifacts_rejected():
    from QCFP_MTF.governance.pure_release_judge import (
        issue_release_verdict,
    )
    bundle = _passing_bundle()
    bundle["replay_result.json"]["release_id"] = "REL-OTHER"
    manifest = _manifest_for(bundle)
    verdict = issue_release_verdict(
        bundle, evidence_manifest=manifest)
    assert verdict["verdict"] == "REJECTED"
    assert verdict["identity_violations"]


def test_judge_partial_identity_not_proven():
    from QCFP_MTF.governance.pure_release_judge import (
        issue_release_verdict,
    )
    bundle = _passing_bundle()
    del bundle["golden_result.json"]["baseline_id"]
    manifest = _manifest_for(bundle)
    verdict = issue_release_verdict(
        bundle, evidence_manifest=manifest)
    assert verdict["verdict"] == "NOT_PROVEN"
    assert "golden_result.json" in verdict["missing_identity"]


def test_judge_bundle_hash_tampered_not_proven():
    from QCFP_MTF.governance.pure_release_judge import (
        issue_release_verdict,
    )
    bundle = _passing_bundle()
    manifest = _manifest_for(bundle)
    manifest["bundle_hash"] = "tampered"
    verdict = issue_release_verdict(
        bundle, evidence_manifest=manifest)
    assert verdict["verdict"] == "NOT_PROVEN"


def test_evidence_pack_read_only_and_identity():
    """SF-3：Pack 只读；mixed identity → PACK_REJECTED 且 artifact 不变。"""
    from QCFP_MTF.governance.pure_release_judge import (
        build_evidence_manifest, validate_pack_identity,
    )
    with _tmp_dir() as d:
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
        assert before == after, "Evidence Pack 不得修改 artifact"
        check = validate_pack_identity(
            bundle, "CHG-TEST-001", "REL-1", "GOV-BASELINE-3")
        assert check["status"] == "PACK_REJECTED"


def test_evidence_pack_missing_identity_not_proven():
    from QCFP_MTF.governance.pure_release_judge import (
        build_evidence_manifest,
    )
    with _tmp_dir() as d:
        bundle_dir = Path(d) / "bundle"
        bundle_dir.mkdir()
        bundle = _passing_bundle()
        del bundle["baseline.json"]["baseline_id"]
        for name, data in bundle.items():
            (bundle_dir / name).write_text(
                json.dumps(data, ensure_ascii=False), encoding="utf-8")
        result = build_evidence_manifest(
            bundle_dir, "CHG-TEST-001", "REL-1", "GOV-BASELINE-3",
            bundle_dir)
        assert result["pack_status"] == "PACK_NOT_PROVEN"


# ------------------ Sprint D #10 Qualification / Promotion（C6 + SF-5） ----

def _release_verdict_artifact():
    return {"verdict": "SOFTWARE_QUALIFIED",
            "certificate": "SOFTWARE-QUALIFIED",
            "change_id": "CHG-TEST-001",
            "baseline_id": "GOV-BASELINE-3",
            "release_id": "REL-1"}


def _promotion_context():
    return {"change_id": "CHG-TEST-001", "release_id": "REL-1",
            "baseline_id": "GOV-BASELINE-3"}


def _promotion_evidence():
    manifest = {"bundle_schema": "EVIDENCE-BUNDLE-2",
                "change_id": "CHG-TEST-001", "release_id": "REL-1",
                "baseline_id": "GOV-BASELINE-3",
                "artifacts": [], "bundle_hash": "x"}
    return {"release_verdict": _release_verdict_artifact(),
            "evidence_manifest": manifest}


def _human_approval_artifact(evidence, target="HUMAN_APPROVED",
                             production_authorized=False,
                             actor_type="HUMAN") -> dict:
    def _h(obj):
        return hashlib.sha256(
            json.dumps(obj, sort_keys=True, ensure_ascii=False,
                       default=str).encode("utf-8")).hexdigest()
    approval = {
        "schema": "HUMAN-APPROVAL-2",
        "approval_id": "AP-1",
        "actor_type": actor_type,
        "approved_by": "human-ops",
        "approved_at": "2026-08-31T00:00:00Z",
        "change_id": "CHG-TEST-001",
        "release_id": "REL-1",
        "baseline_id": "GOV-BASELINE-3",
        "source_state": "PRODUCTION_ELIGIBLE",
        "target_state": target,
        "release_verdict_hash": _h(evidence.get("release_verdict")),
        "evidence_manifest_hash": _h(evidence.get("evidence_manifest")),
        "approval_nonce": "N-1",
        "approval_hash": "",
    }
    if production_authorized:
        approval["production_promotion_authorized"] = True
    payload = {k: v for k, v in approval.items()
               if k not in ("approval_hash", "approval_nonce")}
    approval["approval_hash"] = _h(payload)
    return approval


def test_gate_a_requires_pure_judge_artifact_with_release():
    from QCFP_MTF.governance.qualification_promotion import (
        promotion_verdict,
    )
    ctx = _promotion_context()
    assert promotion_verdict("DEVELOPMENT", "SOFTWARE_QUALIFIED",
                             {}, ctx)["verdict"] == "PROMOTION_BLOCKED"
    ok = promotion_verdict("DEVELOPMENT", "SOFTWARE_QUALIFIED",
                           _release_verdict_artifact(), ctx)
    assert ok["verdict"] == "PROMOTION_OK"
    # fake boolean qualification 不可绕过
    fake = {"canonical_spec": True, "golden": True, "unit": True}
    assert promotion_verdict("DEVELOPMENT", "SOFTWARE_QUALIFIED",
                             fake, ctx)["verdict"] == "PROMOTION_BLOCKED"
    # 旧 release 的 verdict 不能用于新 release 上下文
    old = dict(_release_verdict_artifact(), release_id="REL-OLD")
    assert promotion_verdict("DEVELOPMENT", "SOFTWARE_QUALIFIED",
                             old, ctx)["verdict"] == "PROMOTION_BLOCKED"


def test_gate_a_context_identity_required():
    from QCFP_MTF.governance.qualification_promotion import (
        promotion_verdict,
    )
    incomplete = {"release_id": "REL-1", "baseline_id": "GOV-BASELINE-3"}
    verdict = promotion_verdict("DEVELOPMENT", "SOFTWARE_QUALIFIED",
                                _release_verdict_artifact(), incomplete)
    assert verdict["verdict"] == "PROMOTION_BLOCKED"


def test_promotion_non_adjacent_jumps_blocked():
    from QCFP_MTF.governance.qualification_promotion import (
        promotion_verdict,
    )
    for jump in (("DEVELOPMENT", "SHADOW"),
                 ("DEVELOPMENT", "PRODUCTION_DSS"),
                 ("SOFTWARE_QUALIFIED", "PRODUCTION_ELIGIBLE"),
                 ("SHADOW", "PRODUCTION_DSS")):
        assert promotion_verdict(*jump)["verdict"] == "PROMOTION_BLOCKED"


def test_per_stage_strategy_evidence():
    from QCFP_MTF.governance.qualification_promotion import (
        promotion_verdict,
    )
    assert promotion_verdict("RESEARCH_CANDIDATE", "OOS_VALIDATED",
                             {"research_candidate": True})["verdict"] == \
        "PROMOTION_BLOCKED"
    assert promotion_verdict("RESEARCH_CANDIDATE", "OOS_VALIDATED",
                             {"research_candidate": True,
                              "oos": True})["verdict"] == "PROMOTION_OK"


def test_human_approval_artifact_required_and_bound():
    from QCFP_MTF.governance.qualification_promotion import (
        promotion_verdict,
    )
    evidence = _promotion_evidence()
    ctx = _promotion_context()
    assert promotion_verdict("PRODUCTION_ELIGIBLE", "HUMAN_APPROVED",
                             {}, ctx)["verdict"] == "PROMOTION_BLOCKED"
    ok = promotion_verdict(
        "PRODUCTION_ELIGIBLE", "HUMAN_APPROVED",
        {"human_approval": _human_approval_artifact(evidence),
         **evidence}, ctx)
    assert ok["verdict"] == "PROMOTION_OK"
    # PRODUCTION_DSS 复用同一 approval（production_promotion_authorized）
    authorized = _human_approval_artifact(evidence, production_authorized=True)
    ok_dss = promotion_verdict(
        "HUMAN_APPROVED", "PRODUCTION_DSS",
        {"human_approval": authorized, **evidence}, ctx)
    assert ok_dss["verdict"] == "PROMOTION_OK"


def test_human_approval_wrong_hash_or_actor_blocked():
    from QCFP_MTF.governance.qualification_promotion import (
        promotion_verdict,
    )
    evidence = _promotion_evidence()
    ctx = _promotion_context()
    ai = _human_approval_artifact(evidence, actor_type="AI")
    assert promotion_verdict(
        "PRODUCTION_ELIGIBLE", "HUMAN_APPROVED",
        {"human_approval": ai, **evidence}, ctx)["verdict"] == \
        "PROMOTION_BLOCKED"
    wrong_hash = _human_approval_artifact(evidence)
    wrong_hash["release_verdict_hash"] = "wrong"
    assert promotion_verdict(
        "PRODUCTION_ELIGIBLE", "HUMAN_APPROVED",
        {"human_approval": wrong_hash, **evidence}, ctx)["verdict"] == \
        "PROMOTION_BLOCKED"
    other_release = _human_approval_artifact(evidence)
    other_release["release_id"] = "REL-OTHER"
    assert promotion_verdict(
        "PRODUCTION_ELIGIBLE", "HUMAN_APPROVED",
        {"human_approval": other_release, **evidence}, ctx)["verdict"] == \
        "PROMOTION_BLOCKED"
