# coding: utf-8
"""Phase 4 Governance Closure Gate 单测（FGC-1 + SF-1~SF-5）"""

import json
import tempfile
from pathlib import Path

_IDENTITY = {"change_id": "CHG-P4-TEST", "release_id": "REL-P4-TEST",
             "baseline_id": "GOV-BASELINE-4"}


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                    encoding="utf-8")


def _suite(count=10) -> dict:
    return {"status": "PASS", "exit_code": 0, "collected": count,
            "passed": count, "failed": 0, "errors": 0, "skipped": 0,
            "failure_classification": "PASS", "failures": []}


def _bundle_artifacts() -> dict:
    return {
        "spec_conformance.json": {
            "schema": "SPEC-CONFORMANCE-2", "conformant": True,
            "verdict": "SPEC_CONFORMANT"},
        "baseline.json": {"schema": "BASELINE-GATE-2", "pass": True,
                          "verdict": "BASELINE_PASS"},
        "traceability.json": {"schema": "TRACEABILITY-2", "pass": True,
                              "verdict": "TRACEABILITY_PASS"},
        "change_impact.json": {
            "schema": "CHANGE-IMPACT-2",
            "approved_for_contract": True, "observed_diff_valid": True,
            "observed_tier": "STANDARD",
            "status": "CHANGE_IMPACT_READY"},
        "implementation_contract_result.json": {
            "schema": "CONTRACT-RESULT-2", "verdict": "CONTRACT_OK",
            "pass": True},
        "acceptance_result.json": {
            "schema": "ACCEPTANCE-RESULT-2", "verdict": "ACCEPTANCE_PASS",
            "pass": True},
        "scope_audit.json": {
            "schema": "SCOPE-2", "verdict": "PATCH_ACCEPTED",
            "authority_source": "AUTHORITY_GRAPH", "violations": []},
        "review_report.json": {
            "schema": "REVIEW-2", "verdict": "REVIEW_CLEAN",
            "certification_authority": "None"},
        "review_resolution.json": {
            "schema": "REVIEW-RESOLUTION-2", "verdict": "REVIEW_RESOLVED",
            "open_critical": 0, "open_major": 0,
            "gate": {"allowed": True, "verdict": "REVIEW_RESOLVED"}},
        "fgc_bypass_suite.json": {
            "schema": "FGC-BYPASS-SUITE-1", "all_blocked": True,
            "checks": {"a": True, "b": True, "c": True}},
        "phase4_regression_summary.json": {
            "schema": "PHASE4-REGRESSION-1", "suites": {
                name: _suite() for name in (
                    "phase4_flow", "bypass", "phase1", "phase3",
                    "decision", "governance", "full_core")}},
    }


def _scaffold(root: Path) -> tuple:
    out_dir = root / "phase4"
    bundle_dir = out_dir / "bundle"
    artifacts = _bundle_artifacts()
    for name, data in artifacts.items():
        data = dict(data)
        data.update(_IDENTITY)
        _write(bundle_dir / name, data)
    manifest = {
        "bundle_schema": "EVIDENCE-BUNDLE-2",
        "change_id": _IDENTITY["change_id"],
        "release_id": _IDENTITY["release_id"],
        "baseline_id": _IDENTITY["baseline_id"],
        "artifacts": [{"name": n, "sha256": "x", "schema": "y"}
                      for n in sorted(artifacts)],
        "bundle_hash": "h",
    }
    _write(bundle_dir / "evidence_manifest.json", manifest)
    regression = artifacts["phase4_regression_summary.json"]
    _write(out_dir / "phase4_regression_summary.json", regression)
    _write(out_dir / "evidence_pack_readonly.json", {
        "schema": "EVIDENCE-PACK-READONLY-1",
        "pack_status": "PACK_ACCEPTED", "all_unchanged": True,
        "artifact_count": len(artifacts), "changed_artifacts": []})
    _write(out_dir / "evidence_manifest_verification.json", {
        "schema": "EVIDENCE-MANIFEST-VERIFY-1", "valid": True,
        "all_identity_ok": True, "artifact_count": len(artifacts),
        "problems": []})
    return out_dir, bundle_dir


def test_phase4_acceptance_pass_all_gates():
    from QCFP_MTF.governance.phase4 import phase4_acceptance
    with tempfile.TemporaryDirectory() as d:
        out_dir, bundle_dir = _scaffold(Path(d))
        acceptance = phase4_acceptance(out_dir, bundle_dir)
        assert acceptance["verdict"] == "PHASE4_PASS"
        assert acceptance["freeze_state"] == "GOVERNANCE_FREEZE_CANDIDATE"
        assert acceptance["pass"] is True
        assert acceptance["close_record"]["bypass_to_software_qualified"] == 0
        assert (out_dir / "phase4_acceptance.json").exists()
        assert (out_dir / "phase4_acceptance.md").exists()
        assert (out_dir / "phase4_freeze_record.txt").exists()


def test_missing_artifact_not_proven():
    from QCFP_MTF.governance.phase4 import phase4_acceptance
    with tempfile.TemporaryDirectory() as d:
        out_dir, bundle_dir = _scaffold(Path(d))
        (bundle_dir / "spec_conformance.json").unlink()
        acceptance = phase4_acceptance(out_dir, bundle_dir)
        assert acceptance["verdict"] == "PHASE4_NOT_PROVEN"
        assert acceptance["pass"] is False
        assert "SPEC" in acceptance["missing_evidence"]
        assert acceptance["failures"] == []


def test_failed_baseline_gate_fails_phase():
    from QCFP_MTF.governance.phase4 import phase4_acceptance
    with tempfile.TemporaryDirectory() as d:
        out_dir, bundle_dir = _scaffold(Path(d))
        baseline = json.loads(
            (bundle_dir / "baseline.json").read_text(encoding="utf-8"))
        baseline["verdict"] = "BASELINE_CHANGED"
        baseline["pass"] = False
        _write(bundle_dir / "baseline.json", baseline)
        acceptance = phase4_acceptance(out_dir, bundle_dir)
        assert acceptance["verdict"] == "PHASE4_FAIL"
        assert "BASELINE" in acceptance["failures"]


def test_bypass_escape_derived_from_suite_not_hardcoded():
    from QCFP_MTF.governance.phase4 import phase4_acceptance
    with tempfile.TemporaryDirectory() as d:
        out_dir, bundle_dir = _scaffold(Path(d))
        regression = json.loads(
            (out_dir / "phase4_regression_summary.json")
            .read_text(encoding="utf-8"))
        regression["suites"]["bypass"] = {
            "status": "FAIL", "exit_code": 1, "collected": 3,
            "passed": 2, "failed": 1, "errors": 0, "skipped": 0,
            "failure_classification": "ASSERTION_FAILURE",
            "failures": []}
        _write(out_dir / "phase4_regression_summary.json", regression)
        acceptance = phase4_acceptance(out_dir, bundle_dir)
        assert acceptance["verdict"] == "PHASE4_FAIL"
        bypass = acceptance["gates"]["ZERO_BYPASS"]
        assert bypass["status"] == "FAIL"
        assert bypass["verdict"] == "BYPASS_ESCAPED"
        assert bypass["evidence"]["bypass_escaped"] == 1


def test_missing_regression_suite_not_proven():
    from QCFP_MTF.governance.phase4 import phase4_acceptance
    with tempfile.TemporaryDirectory() as d:
        out_dir, bundle_dir = _scaffold(Path(d))
        regression = json.loads(
            (out_dir / "phase4_regression_summary.json")
            .read_text(encoding="utf-8"))
        del regression["suites"]["full_core"]
        _write(out_dir / "phase4_regression_summary.json", regression)
        acceptance = phase4_acceptance(out_dir, bundle_dir)
        assert acceptance["verdict"] == "PHASE4_NOT_PROVEN"
        assert "REGRESSION" in acceptance["missing_evidence"]


def test_pack_not_readonly_fails_sf3_gate():
    from QCFP_MTF.governance.phase4 import phase4_acceptance
    with tempfile.TemporaryDirectory() as d:
        out_dir, bundle_dir = _scaffold(Path(d))
        _write(out_dir / "evidence_pack_readonly.json", {
            "schema": "EVIDENCE-PACK-READONLY-1",
            "pack_status": "PACK_REJECTED", "all_unchanged": False,
            "changed_artifacts": ["baseline.json"]})
        acceptance = phase4_acceptance(out_dir, bundle_dir)
        assert acceptance["verdict"] == "PHASE4_FAIL"
        assert "EVIDENCE_PACK_SF3" in acceptance["failures"]


def test_identity_verification_failure_fails_sf4_gate():
    from QCFP_MTF.governance.phase4 import phase4_acceptance
    with tempfile.TemporaryDirectory() as d:
        out_dir, bundle_dir = _scaffold(Path(d))
        _write(out_dir / "evidence_manifest_verification.json", {
            "schema": "EVIDENCE-MANIFEST-VERIFY-1", "valid": False,
            "all_identity_ok": False, "artifact_count": 1,
            "problems": ["baseline.json hash 不匹配"]})
        acceptance = phase4_acceptance(out_dir, bundle_dir)
        assert acceptance["verdict"] == "PHASE4_FAIL"
        assert "MANIFEST_IDENTITY" in acceptance["failures"]
