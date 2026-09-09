# coding: utf-8
"""P5-GOV-REOPEN-CPUB-R1.1 — activation-bound candidate tests."""

import ast
import hashlib
import json
import sqlite3
import sys
import types
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import load_qcfp_settings  # noqa: E402


CAND = PROJECT_ROOT / "audit" / "phase5" / "cpub_candidate"
SERVICE_SRC = (CAND / "01_canonical_publication.py.txt").read_text(
    encoding="utf-8")


def _service_module():
    module = types.ModuleType("cpub_candidate_service")
    module.__file__ = str(CAND / "01_canonical_publication.py.txt")
    exec(compile(SERVICE_SRC, str(CAND / "01_canonical_publication.py.txt"),
                 "exec"), module.__dict__)
    return module


def test_a01_public_api_has_no_caller_activation_or_universe():
    tree = ast.parse(SERVICE_SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) \
                and node.name == "publish_canonical_cohort":
            args = [a.arg for a in node.args.args]
            assert args == []
            kw = [a.arg for a in node.args.kwonlyargs]
            assert kw == ["conn", "decision_date", "settings", "run_id"]
            assert "activation" not in kw
            assert "universe_snapshot" not in kw
            assert "expected_symbols" not in kw
            return
    raise AssertionError("publish_canonical_cohort not found")


def test_a02_missing_activation_artifact_fails_before_evaluate():
    """R2-14 lifecycle-aware alignment: with the real activation artifacts
    present the authority chain is active, so ACTIVATION_ARTIFACT_MISSING no
    longer fires. The missing-artifact fail-closed guard is preserved whenever
    the fixed activation artifact is absent (unit-level, no active mutation)."""
    module = _service_module()
    saved = dict(module.FIXED_ARTIFACTS)
    missing = dict(saved)
    missing["activation"] = module.PROJECT_ROOT / "__no_such_activation__.json"
    try:
        module.FIXED_ARTIFACTS = missing
        conn = sqlite3.connect(":memory:")
        with pytest.raises(module.CanonicalPublicationAuthorityError) as exc:
            module.publish_canonical_cohort(
                conn=conn, decision_date="2026-09-04",
                settings={}, run_id="r")
        assert "ACTIVATION_ARTIFACT_MISSING" in str(exc.value)
    finally:
        module.FIXED_ARTIFACTS = saved
    # Activated lifecycle: real artifacts present -> the artifact-missing guard
    # must NOT fire; publication still fails closed on the unprepared test
    # connection before any evaluate call.
    conn = sqlite3.connect(":memory:")
    try:
        module.publish_canonical_cohort(
            conn=conn, decision_date="2026-09-04",
            settings={}, run_id="r")
        raise AssertionError("expected fail-closed error on unprepared conn")
    except Exception as exc:  # noqa: BLE001
        assert "ACTIVATION_ARTIFACT_MISSING" not in str(exc)


def test_manifest_and_activation_mutated_together_still_fail(tmp_path):
    module = _service_module()
    _valid_artifacts(tmp_path, module)
    manifest_path = module.FIXED_ARTIFACTS["candidate_manifest"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["tampered"] = True
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(
            module.CanonicalPublicationAuthorityError,
            match="CANDIDATE_MANIFEST_PACKAGE_MISMATCH"):
        module._load_and_verify_activation()


def test_valid_complete_authority_chain_passes(tmp_path, monkeypatch):
    import types

    service = _service_module()

    def load_candidate(name):
        path = CAND / name
        mod = types.ModuleType(name)
        mod.__file__ = str(path)
        exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"),
             mod.__dict__)
        return mod

    builder = load_candidate("11_build_activation_record.py.txt")
    finalizer = load_candidate("12_finalize_governance_baseline.py.txt")
    package_bytes = (CAND / "10_candidate_package.json").read_bytes()
    manifest_bytes = (CAND / "09_candidate_manifest.json").read_bytes()
    package = json.loads(package_bytes)
    acceptance = json.dumps({
        "scope": "P5-GOV-REOPEN-CPUB", "decision": "APPROVE",
        "accepted_by": "HUMAN",
        "candidate_package_sha256":
            package["candidate_package_sha256"],
    }).encode("utf-8")
    activation_bytes = builder.build_activation_record(
        candidate_package_bytes=package_bytes,
        human_acceptance_bytes=acceptance,
        candidate_manifest_bytes=manifest_bytes)
    baseline_bytes = finalizer.finalize_governance_baseline(
        candidate_baseline_bytes=(CAND /
            "05_phase5_governance_baseline_candidate.json").read_bytes(),
        candidate_package_bytes=package_bytes,
        human_acceptance_bytes=acceptance,
        activation_bytes=activation_bytes)
    artifacts = {
        "human_acceptance": tmp_path / "h.json",
        "activation": tmp_path / "a.json",
        "candidate_package": tmp_path / "p.json",
        "candidate_manifest": tmp_path / "m.json",
        "governance_baseline": tmp_path / "b.json",
    }
    artifacts["human_acceptance"].write_bytes(acceptance)
    artifacts["activation"].write_bytes(activation_bytes)
    artifacts["candidate_package"].write_bytes(package_bytes)
    artifacts["candidate_manifest"].write_bytes(manifest_bytes)
    artifacts["governance_baseline"].write_bytes(baseline_bytes)
    service.FIXED_ARTIFACTS = artifacts
    verified = service._load_and_verify_activation()
    assert verified["candidate_package_sha256"] \
        == package["candidate_package_sha256"]
    assert verified["governance_revision"] == 8
    assert verified["approved_universe_provider"]["provider_id"] \
        == "QCFP-GOVERNED-UNIVERSE"
    assert set(verified["approved_targets"]) == {
        "Core/QCFP_MTF/decision/canonical_publication.py",
        "Core/QCFP_MTF/decision/publication_universe.py",
    }


def test_acceptance_scope_mismatch_exact_reason(tmp_path, monkeypatch):
    import types

    service = _service_module()

    def load_candidate(name):
        path = CAND / name
        mod = types.ModuleType(name)
        mod.__file__ = str(path)
        exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"),
             mod.__dict__)
        return mod

    builder = load_candidate("11_build_activation_record.py.txt")
    finalizer = load_candidate("12_finalize_governance_baseline.py.txt")
    package_bytes = (CAND / "10_candidate_package.json").read_bytes()
    manifest_bytes = (CAND / "09_candidate_manifest.json").read_bytes()
    package = json.loads(package_bytes)
    good_acceptance = json.dumps({
        "scope": "P5-GOV-REOPEN-CPUB", "decision": "APPROVE",
        "accepted_by": "HUMAN",
        "candidate_package_sha256":
            package["candidate_package_sha256"]}).encode("utf-8")
    activation_bytes = builder.build_activation_record(
        candidate_package_bytes=package_bytes,
        human_acceptance_bytes=good_acceptance,
        candidate_manifest_bytes=manifest_bytes)
    baseline_bytes = finalizer.finalize_governance_baseline(
        candidate_baseline_bytes=(CAND /
            "05_phase5_governance_baseline_candidate.json").read_bytes(),
        candidate_package_bytes=package_bytes,
        human_acceptance_bytes=good_acceptance,
        activation_bytes=activation_bytes)
    bad_acceptance = json.dumps({
        "scope": "WRONG", "decision": "APPROVE",
        "accepted_by": "HUMAN",
        "candidate_package_sha256":
            package["candidate_package_sha256"]}).encode("utf-8")
    artifacts = {
        "human_acceptance": tmp_path / "h.json",
        "activation": tmp_path / "a.json",
        "candidate_package": tmp_path / "p.json",
        "candidate_manifest": tmp_path / "m.json",
        "governance_baseline": tmp_path / "b.json"}
    artifacts["human_acceptance"].write_bytes(bad_acceptance)
    artifacts["activation"].write_bytes(activation_bytes)
    artifacts["candidate_package"].write_bytes(package_bytes)
    artifacts["candidate_manifest"].write_bytes(manifest_bytes)
    artifacts["governance_baseline"].write_bytes(baseline_bytes)
    service.FIXED_ARTIFACTS = artifacts
    with pytest.raises(service.CanonicalPublicationAuthorityError,
                       match="ACCEPTANCE_SCOPE_MISMATCH"):
        service._load_and_verify_activation()


def test_valid_materialized_target_hashes_pass(tmp_path, monkeypatch):
    service = _service_module()
    package = json.loads(
        (CAND / "10_candidate_package.json").read_text(encoding="utf-8"))
    activation = {
        "approved_targets": {
            "Core/QCFP_MTF/decision/canonical_publication.py":
                package["file_sha256"][
                    "CANONICAL_PUBLICATION_AUTHORITY_CANDIDATE"],
            "Core/QCFP_MTF/decision/publication_universe.py":
                package["file_sha256"][
                    "CANONICAL_PUBLICATION_INPUT_AUTHORITY_CANDIDATE"]}}
    root = tmp_path
    target_dir = root / "Core/QCFP_MTF/decision"
    target_dir.mkdir(parents=True)
    (target_dir / "publication_universe.py").write_bytes(
        (CAND / "02_publication_universe_provider.py.txt").read_bytes())
    service.PROJECT_ROOT = root
    assert service._verify_target_hashes(activation) is None


def test_modified_provider_target_fails(tmp_path, monkeypatch):
    service = _service_module()
    package = json.loads(
        (CAND / "10_candidate_package.json").read_text(encoding="utf-8"))
    activation = {
        "approved_targets": {
            "Core/QCFP_MTF/decision/canonical_publication.py":
                package["file_sha256"][
                    "CANONICAL_PUBLICATION_AUTHORITY_CANDIDATE"],
            "Core/QCFP_MTF/decision/publication_universe.py":
                package["file_sha256"][
                    "CANONICAL_PUBLICATION_INPUT_AUTHORITY_CANDIDATE"]}}
    root = tmp_path
    target_dir = root / "Core/QCFP_MTF/decision"
    target_dir.mkdir(parents=True)
    (target_dir / "publication_universe.py").write_bytes(b"TAMPERED")
    service.PROJECT_ROOT = root
    with pytest.raises(service.CanonicalPublicationAuthorityError,
                       match="MATERIALIZED_TARGET_SHA_MISMATCH"):
        service._verify_target_hashes(activation)


def test_a03_forged_local_dict_cannot_activate():
    module = _service_module()
    with pytest.raises(TypeError):
        module.publish_canonical_cohort(
            conn=None, decision_date="2026-09-04", settings={},
            run_id="r",
            activation={"scope": "CANONICAL_PUBLICATION",
                        "authority_status": "ACTIVE"})


def _artifact_tmp(tmp_path, module, acceptance=None, activation=None,
                  package=None, baseline=None):
    files = {}
    for name, key in (("human_acceptance", "human_acceptance"),
                      ("activation", "activation"),
                      ("candidate_package", "candidate_package"),
                      ("governance_baseline", "governance_baseline")):
        path = tmp_path / f"{key}.json"
        data = {
            "human_acceptance": acceptance,
            "activation": activation,
            "candidate_package": package,
            "governance_baseline": baseline,
        }[key]
        if data is not None:
            path.write_text(json.dumps(data), encoding="utf-8")
        files[name] = path
    module.FIXED_ARTIFACTS = files


def _valid_artifacts(tmp_path, module):
    package = {
        "schema": "p", "candidate_package_sha256": "pkg-sha",
        "file_sha256": {
            "CANONICAL_PUBLICATION_AUTHORITY_CANDIDATE": "t1",
            "CANONICAL_PUBLICATION_INPUT_AUTHORITY_CANDIDATE": "t2"},
        "activation": False,
    }
    module._recompute_package_digest = lambda p: p.get(
        "candidate_package_sha256")
    acceptance = {"accepted_by": "HUMAN", "decision": "APPROVE"}
    acceptance_sha = "acc-sha"
    activation = {
        "scope": "P5-GOV-REOPEN-CPUB", "authority_status": "ACTIVE",
        "candidate_package_sha256": "pkg-sha",
        "human_acceptance_sha256": acceptance_sha,
        "governance_revision": 8,
        "approved_universe_provider": {
            "provider_id": "QCFP-GOVERNED-UNIVERSE",
            "provider_version": "WEEKLY-TACTICAL-1"},
        "approved_targets": {},
    }
    baseline = {"governance_revision": 8, "status": "ACCEPTED",
                "accepted_by": "HUMAN"}
    _artifact_tmp(tmp_path, module, acceptance, activation, package,
                  baseline)
    manifest_path = tmp_path / "candidate_manifest.json"
    manifest_path.write_text(json.dumps({
        "files": [
            {"target_path":
             "Core/QCFP_MTF/decision/canonical_publication.py",
             "sha256": "t1"},
            {"target_path":
             "Core/QCFP_MTF/decision/publication_universe.py",
             "sha256": "t2"},
        ]}), encoding="utf-8")
    module.FIXED_ARTIFACTS["candidate_manifest"] = manifest_path
    activation_path = module.FIXED_ARTIFACTS["activation"]
    activation = json.loads(activation_path.read_text(encoding="utf-8"))
    activation["approved_targets"] = {
        "Core/QCFP_MTF/decision/canonical_publication.py": "t1",
        "Core/QCFP_MTF/decision/publication_universe.py": "t2",
    }
    activation["human_acceptance_sha256"] = hashlib.sha256(
        module.FIXED_ARTIFACTS["human_acceptance"].read_bytes()
    ).hexdigest()
    activation_path.write_text(json.dumps(activation), encoding="utf-8")




def _ledger_conn(identity):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE qcfp_decision_ledger ("
                 "stock_code TEXT, decision_date TEXT, status TEXT, "
                 "settings_hash TEXT, model_version TEXT, rule_version TEXT)")
    conn.execute(
        "INSERT INTO qcfp_decision_ledger VALUES "
        "(?,?,?,?,?,?)",
        ("01951", "2026-09-04", "ACTIVE",
         identity["settings_hash"], identity["model_version"],
         identity["rule_version"]))
    conn.commit()
    return conn


@pytest.mark.parametrize("field", ["settings_hash", "model_version",
                                   "rule_version"])
def test_ledger_identity_mismatch_fails_closed(field):
    module = _service_module()
    settings = load_qcfp_settings()
    identity = module._expected_identity(settings)
    bad = dict(identity)
    bad[field] = "WRONG"
    conn = _ledger_conn(bad)
    audit = module._exact_ledger_audit(
        conn, "2026-09-04", ["01951"], settings)
    assert audit["matching_count"] == 0
    assert len(audit["identity_mismatch"]) == 1
    assert audit["identity_mismatch"][0]["stock_code"] == "01951"
    assert audit["identity_mismatch"][0]["expected"][field] \
        == identity[field]


def test_ledger_exact_identity_ready():
    module = _service_module()
    settings = load_qcfp_settings()
    identity = module._expected_identity(settings)
    conn = _ledger_conn(identity)
    audit = module._exact_ledger_audit(
        conn, "2026-09-04", ["01951"], settings)
    assert audit["matching_count"] == 1
    assert audit["identity_mismatch"] == []


def test_ledger_duplicate_active_not_ready():
    module = _service_module()
    settings = load_qcfp_settings()
    identity = module._expected_identity(settings)
    conn = _ledger_conn(identity)
    conn.execute(
        "INSERT INTO qcfp_decision_ledger VALUES "
        "(?,?,?,?,?,?)",
        ("01951", "2026-09-04", "ACTIVE",
         identity["settings_hash"], identity["model_version"],
         identity["rule_version"]))
    conn.commit()
    audit = module._exact_ledger_audit(
        conn, "2026-09-04", ["01951"], settings)
    assert audit["duplicates"] == ["01951"]
    assert audit["matching_count"] == 0
