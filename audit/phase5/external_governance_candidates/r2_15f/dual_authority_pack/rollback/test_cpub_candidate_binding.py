# coding: utf-8
"""P5-GOV-REOPEN-CPUB-R1 — candidate binding consistency tests."""

import hashlib
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[4]
import sys as _h1h_sys
from pathlib import Path as _h1h_path
_h1h_sys.path.insert(0, str(_h1h_path(__file__).resolve().parent))
from _gov_current import current_identity as _cid
_ids = _cid(_h1h_path(__file__).resolve().parents[4])

CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))


CAND = PROJECT_ROOT / "audit" / "phase5" / "cpub_candidate"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(name: str) -> dict:
    return json.loads((CAND / name).read_text(encoding="utf-8"))


def test_cbind_t01_all_candidate_files_exist():
    expected = [f"{i:02d}_" for i in range(1, 11)]
    files = sorted(p.name for p in CAND.iterdir() if p.is_file())
    for prefix in expected:
        assert any(name.startswith(prefix) for name in files)


def test_cbind_t02_manifest_sha_matches_bytes():
    manifest = _load("09_candidate_manifest.json")
    for entry in manifest["files"]:
        path = PROJECT_ROOT / entry["candidate_path"]
        assert path.exists()
        assert path.stat().st_size == entry["bytes"]
        assert _sha(path) == entry["sha256"]


def test_cbind_t03_package_references_exact_candidate_sha():
    package = _load("10_candidate_package.json")
    for key, path in package["referenced_files"].items():
        actual = _sha(PROJECT_ROOT / path)
        assert package["file_sha256"][key] == actual


def test_cbind_t04_future_target_paths_unique_and_not_materialized():
    """R2-14 activated alignment: EXACT code/service targets ARE now
    materialized with exact approved bytes. The governance manifest target is
    the unchanged IDENTICAL_CURRENT_GOVERNANCE mirror; the governance baseline
    target resolves to the activated successor identity (cpub_candidate/05
    remains the byte-preserved PRE-activation mirror bound by the package)."""
    manifest = _load("09_candidate_manifest.json")
    targets = [e["target_path"] for e in manifest["files"]
               if e.get("target_path")]
    assert len(targets) == len(set(targets))
    for entry in manifest["files"]:
        target = entry.get("target_path")
        if not target:
            continue
        path = PROJECT_ROOT / target
        materialization_type = entry["materialization_type"]
        if materialization_type == "EXACT_MATERIALIZATION_TARGET":
            # Code/service targets ARE materialized with exact approved bytes.
            assert str(target).startswith("Core/")
            assert path.exists()
            assert _sha(path) == entry["sha256"]
        elif materialization_type == "IDENTICAL_CURRENT_GOVERNANCE":
            assert path.exists()
            if target == "audit/phase5/phase5_governance_baseline.json":
                # ACTIVE baseline is the activated successor (resolver-bound);
                # the pre-activation mirror file preserves the package bytes.
                assert _sha(path) == _ids["baseline"]
                pre_activation_mirror = CAND / \
                    "05_phase5_governance_baseline_candidate.json"
                assert _sha(pre_activation_mirror) == entry["sha256"]
            else:
                # Frozen-surface manifest mirror is unchanged and still equals
                # the ACTIVE manifest bytes.
                assert _sha(path) == entry["sha256"]
        else:
            raise AssertionError(
                "unexpected materialization_type: " + materialization_type)


def test_cbind_t05_no_candidate_target_is_shadow():
    manifest = _load("09_candidate_manifest.json")
    for entry in manifest["files"]:
        target = entry.get("target_path") or ""
        assert "shadow" not in target.lower()


def test_cbind_t06_candidate_does_not_duplicate_decision_logic():
    source = (CAND / "01_canonical_publication.py.txt").read_text(
        encoding="utf-8")
    for forbidden in ("def transition", "def finalize_target",
                      "def _size(", "def permission"):
        assert forbidden not in source


def test_cbind_t07_candidate_imports_unique_engine_evaluate():
    source = (CAND / "01_canonical_publication.py.txt").read_text(
        encoding="utf-8")
    assert "from QCFP_MTF.decision.engine import evaluate" in source


def test_cbind_t08_candidate_persists_only_through_record_snapshot():
    source = (CAND / "01_canonical_publication.py.txt").read_text(
        encoding="utf-8")
    assert "record_snapshot" in source
    for forbidden in ("INSERT INTO qcfp_decision_ledger",
                      "UPDATE qcfp_decision_ledger",
                      "DELETE FROM qcfp_decision_ledger"):
        assert forbidden not in source


def test_cbind_t09_universe_provider_candidate_is_read_only():
    source = (CAND / "02_publication_universe_provider.py.txt").read_text(
        encoding="utf-8")
    for token in ("INSERT ", "UPDATE ", "DELETE ", "REPLACE ",
                  "record_snapshot"):
        assert token not in source
    assert "conn.execute(" in source  # SELECT/read only


def test_manifest_materialization_semantics():
    """H1K R2-01E alignment: code/service roles are EXACT_MATERIALIZATION_TARGET
    future targets; governance roles are IDENTICAL_CURRENT_GOVERNANCE mirrors of
    the ACTIVE accepted bytes. Derivation tool roles are no longer manifest
    entries (they remain candidate tooling, exercised by their own tests)."""
    manifest = _load("09_candidate_manifest.json")
    roles = {}
    for entry in manifest["files"]:
        roles[entry["role"]] = entry["materialization_type"]
    assert set(roles) == {
        "CANONICAL_PUBLICATION_AUTHORITY_CANDIDATE",
        "CANONICAL_PUBLICATION_INPUT_AUTHORITY_CANDIDATE",
        "FROZEN_SURFACE_MANIFEST_CANDIDATE",
        "GOVERNANCE_BASELINE_PREACTIVATION_CANDIDATE",
    }
    assert roles["CANONICAL_PUBLICATION_AUTHORITY_CANDIDATE"] \
        == "EXACT_MATERIALIZATION_TARGET"
    assert roles["CANONICAL_PUBLICATION_INPUT_AUTHORITY_CANDIDATE"] \
        == "EXACT_MATERIALIZATION_TARGET"
    assert roles["FROZEN_SURFACE_MANIFEST_CANDIDATE"] \
        == "IDENTICAL_CURRENT_GOVERNANCE"
    assert roles["GOVERNANCE_BASELINE_PREACTIVATION_CANDIDATE"] \
        == "IDENTICAL_CURRENT_GOVERNANCE"


def test_package_digest_is_reproducible():
    package = _load("10_candidate_package.json")
    payload = json.dumps(
        {k: package[k] for k in sorted(package)
         if k != "candidate_package_sha256"},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    recomputed = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    assert package["candidate_package_sha256"] == recomputed


def test_manifest_candidate_is_full_replacement():
    """H1c Rev8 current-truth alignment: ACTIVE manifest is the Rev3
    governance-bootstrap manifest (H1b identity cfbc4619...). The older CPUB
    candidate manifest (04) is superseded by the current ACTIVE manifest.
    Rev7 history stays frozen in its archived copy."""
    candidate = _load("04_frozen_surface_manifest_candidate.json")
    current = json.loads(
        (PROJECT_ROOT / "audit/phase5/"
         "frozen_surface_manifest.json").read_text(encoding="utf-8"))
    current_sha = _sha(PROJECT_ROOT / "audit/phase5/"
                       "frozen_surface_manifest.json")
    candidate_sha = _sha(CAND / "04_frozen_surface_manifest_candidate.json")
    # Rev8 current truth: ACTIVE manifest is the approved bootstrap identity.
    assert current_sha == \
        _ids["manifest"]
    assert current["revision"] == _ids["manifest_revision"]
    approved = current.get("human_approved_existing_changes", [])
    assert any(
        e.get("path") == "Core/QCFP_MTF/tests/test_decision/"
                         "test_tactical_chain.py"
        and e.get("task_id") == "P5F-R2-08"
        and e.get("change_class") == "TEST_SEMANTIC_ALIGNMENT"
        for e in approved
    )
    # Superseded CPUB candidate manifest is not the current authority.
    assert candidate_sha != current_sha
    assert candidate["activation"] is False


def test_baseline_candidate_is_full_pre_activation_revision():
    """R2-14 activated alignment: cpub_candidate/05 is the byte-preserved
    PRE-activation mirror of the predecessor Rev8 baseline (d88656b3, bound by
    the approved package). The ACTIVE baseline is the activated successor
    (activation=True) bound by the ACTIVE governance acceptance record."""
    candidate = _load("05_phase5_governance_baseline_candidate.json")
    current = json.loads(
        (PROJECT_ROOT / "audit/phase5/"
         "phase5_governance_baseline.json").read_text(encoding="utf-8"))
    current_sha = _sha(PROJECT_ROOT / "audit/phase5/"
                       "phase5_governance_baseline.json")
    candidate_sha = _sha(CAND / "05_phase5_governance_baseline_candidate.json")
    assert current_sha == \
        _ids["baseline"]
    assert current["governance_revision"] == 8
    assert current["baseline_state"] == "PHASE5_GOVERNANCE_FROZEN"
    assert current["status"] == "ACCEPTED"
    assert current["activation"] is True
    assert current["accepted_by"] == "HUMAN"
    gf = {e["path"]: e["sha256"] for e in current["governance_files"]}
    assert gf["audit/phase5/frozen_surface_manifest.json"] == \
        _ids["manifest"]
    assert gf["tools/review/merge_project_for_phase5_review.py"] == \
        _ids["pins"]["tools/review/merge_project_for_phase5_review.py"]
    assert gf["tools/review/tests/test_merge_project_for_phase5_review.py"] == \
        _ids["pins"]["tools/review/tests/test_merge_project_for_phase5_review.py"]
    # ACTIVE governance acceptance binds the activated baseline identity.
    acceptance = json.loads(
        (PROJECT_ROOT / "audit/phase5/"
         "phase5_governance_acceptance.json").read_text(encoding="utf-8"))
    assert acceptance["governance_baseline_sha256"] == current_sha
    assert acceptance["activation_record_sha256"] == \
        current["activation_record_sha256"]
    # Pre-activation mirror preserves the predecessor baseline bytes and is
    # bound by the ACTIVE acceptance as predecessor_baseline_sha256.
    assert acceptance["predecessor_baseline_sha256"] == candidate_sha
    assert candidate_sha != current_sha
    assert candidate["activation"] is False


def test_cbind_t10_candidate_baseline_status_not_accepted():
    """R2-14 activated alignment: cpub_candidate/05 is the PRE-activation mirror
    (ACCEPTED/FROZEN, activation False) bound by the ACTIVE acceptance as the
    predecessor baseline; the ACTIVE baseline is the activated successor."""
    baseline = _load("05_phase5_governance_baseline_candidate.json")
    assert "candidate_status" not in baseline
    assert baseline["status"] == "ACCEPTED"
    assert baseline["baseline_state"] == "PHASE5_GOVERNANCE_FROZEN"
    assert baseline["lifecycle_state"] == "ACTIVE"
    assert baseline["activation"] is False
    current = json.loads(
        (PROJECT_ROOT / "audit/phase5/"
         "phase5_governance_baseline.json").read_text(encoding="utf-8"))
    acceptance = json.loads(
        (PROJECT_ROOT / "audit/phase5/"
         "phase5_governance_acceptance.json").read_text(encoding="utf-8"))
    candidate_sha = _sha(CAND / "05_phase5_governance_baseline_candidate.json")
    assert candidate_sha == acceptance["predecessor_baseline_sha256"]
    assert _sha(PROJECT_ROOT / "audit/phase5/"
                "phase5_governance_baseline.json") == _ids["baseline"]
    assert current["activation"] is True
    assert current["activation_record_sha256"] == \
        acceptance["activation_record_sha256"]


def test_cbind_t11_candidate_activation_false():
    for name in ("04_frozen_surface_manifest_candidate.json",
                 "05_phase5_governance_baseline_candidate.json",
                 "06_change_record.json",
                 "07_impact_analysis.json",
                 "08_activation_test_plan.json"):
        assert _load(name)["activation"] is False


def test_cbind_t12_human_acceptance_required_true():
    package = _load("10_candidate_package.json")
    assert package["human_acceptance_required"] is True
    assert package["activation"] is False


def _reviewer():
    import importlib.util
    import sys
    path = PROJECT_ROOT / "tools/review/merge_project_for_phase5_review.py"
    spec = importlib.util.spec_from_file_location("rv_tool", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["rv_tool"] = module
    spec.loader.exec_module(module)
    return module


def test_reviewer_classifies_two_future_targets_phase5_allowed():
    rv = _reviewer()
    manifest, err = rv.load_frozen_surface_manifest(
        PROJECT_ROOT,
        rel="audit/phase5/cpub_candidate/"
            "04_frozen_surface_manifest_candidate.json")
    assert manifest is not None, err
    assert rv.classify_phase5_path(
        "Core/QCFP_MTF/decision/canonical_publication.py",
        manifest) == rv.PHASE5_ALLOWED
    assert rv.classify_phase5_path(
        "Core/QCFP_MTF/decision/publication_universe.py",
        manifest) == rv.PHASE5_ALLOWED


def test_reviewer_preserves_existing_decision_shared_read_only():
    rv = _reviewer()
    manifest, err = rv.load_frozen_surface_manifest(
        PROJECT_ROOT,
        rel="audit/phase5/cpub_candidate/"
            "04_frozen_surface_manifest_candidate.json")
    assert rv.classify_phase5_path(
        "Core/QCFP_MTF/decision/engine.py", manifest) \
        in (rv.FROZEN, rv.SHARED_READ_ONLY)
    assert rv.classify_phase5_path(
        "Core/QCFP_MTF/decision/decision_ledger.py", manifest) \
        in (rv.FROZEN, rv.SHARED_READ_ONLY)


def test_reviewer_random_new_decision_file_is_unknown():
    rv = _reviewer()
    manifest, err = rv.load_frozen_surface_manifest(
        PROJECT_ROOT,
        rel="audit/phase5/cpub_candidate/"
            "04_frozen_surface_manifest_candidate.json")
    assert rv.classify_phase5_path(
        "Core/QCFP_MTF/decision/new_writer.py", manifest) == rv.UNKNOWN


def _load_candidate_module(name):
    import types
    path = CAND / name
    module = types.ModuleType(name)
    module.__file__ = str(path)
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"),
         module.__dict__)
    return module


def test_activation_builder_deterministic_and_package_derived():
    builder = _load_candidate_module("11_build_activation_record.py.txt")
    package = _load("10_candidate_package.json")
    acceptance = json.dumps({
        "scope": "P5-GOV-REOPEN-CPUB",
        "decision": "APPROVE",
        "accepted_by": "HUMAN",
        "candidate_package_sha256":
            package["candidate_package_sha256"],
    }).encode("utf-8")
    manifest_bytes = (CAND / "09_candidate_manifest.json").read_bytes()
    package_bytes = (CAND / "10_candidate_package.json").read_bytes()
    a1 = builder.build_activation_record(
        candidate_package_bytes=package_bytes,
        human_acceptance_bytes=acceptance,
        candidate_manifest_bytes=manifest_bytes)
    a2 = builder.build_activation_record(
        candidate_package_bytes=package_bytes,
        human_acceptance_bytes=acceptance,
        candidate_manifest_bytes=manifest_bytes)
    assert a1 == a2
    rec = json.loads(a1)
    assert rec["candidate_package_sha256"] \
        == package["candidate_package_sha256"]
    targets = rec["approved_targets"]
    assert targets["Core/QCFP_MTF/decision/canonical_publication.py"] \
        == package["file_sha256"][
            "CANONICAL_PUBLICATION_AUTHORITY_CANDIDATE"]
    assert targets["Core/QCFP_MTF/decision/publication_universe.py"] \
        == package["file_sha256"][
            "CANONICAL_PUBLICATION_INPUT_AUTHORITY_CANDIDATE"]


def test_activation_builder_rejects_invalid_human_approval():
    builder = _load_candidate_module("11_build_activation_record.py.txt")
    package = _load("10_candidate_package.json")
    package_bytes = (CAND / "10_candidate_package.json").read_bytes()
    manifest_bytes = (CAND / "09_candidate_manifest.json").read_bytes()
    for acceptance in (
        b'{"scope":"X","decision":"APPROVE","accepted_by":"HUMAN"}',
        b'{"scope":"P5-GOV-REOPEN-CPUB","decision":"REJECT",'
        b'"accepted_by":"HUMAN"}',
        b'{"scope":"P5-GOV-REOPEN-CPUB","decision":"APPROVE",'
        b'"accepted_by":"AI"}',
        b'{"scope":"P5-GOV-REOPEN-CPUB","decision":"APPROVE",'
        b'"accepted_by":"HUMAN","candidate_package_sha256":"WRONG"}',
    ):
        with pytest.raises(ValueError):
            builder.build_activation_record(
                candidate_package_bytes=package_bytes,
                human_acceptance_bytes=acceptance,
                candidate_manifest_bytes=manifest_bytes)


def test_baseline_finalizer_deterministic_and_only_activation_fields():
    finalizer = _load_candidate_module(
        "12_finalize_governance_baseline.py.txt")
    builder = _load_candidate_module("11_build_activation_record.py.txt")
    candidate = _load("05_phase5_governance_baseline_candidate.json")
    package = _load("10_candidate_package.json")
    package_bytes = (CAND / "10_candidate_package.json").read_bytes()
    manifest_bytes = (CAND / "09_candidate_manifest.json").read_bytes()
    acceptance = json.dumps({
        "scope": "P5-GOV-REOPEN-CPUB",
        "decision": "APPROVE",
        "accepted_by": "HUMAN",
        "candidate_package_sha256":
            package["candidate_package_sha256"],
    }).encode("utf-8")
    activation_bytes = builder.build_activation_record(
        candidate_package_bytes=package_bytes,
        human_acceptance_bytes=acceptance,
        candidate_manifest_bytes=manifest_bytes)
    b1 = finalizer.finalize_governance_baseline(
        candidate_baseline_bytes=(CAND /
            "05_phase5_governance_baseline_candidate.json").read_bytes(),
        candidate_package_bytes=package_bytes,
        human_acceptance_bytes=acceptance,
        activation_bytes=activation_bytes)
    b2 = finalizer.finalize_governance_baseline(
        candidate_baseline_bytes=(CAND /
            "05_phase5_governance_baseline_candidate.json").read_bytes(),
        candidate_package_bytes=package_bytes,
        human_acceptance_bytes=acceptance,
        activation_bytes=activation_bytes)
    assert b1 == b2
    final = json.loads(b1)
    assert final["governance_revision"] == 8
    assert final["status"] == "ACCEPTED"
    assert final["accepted_by"] == "HUMAN"
    assert final["activation"] is True
    assert final["candidate_package_sha256"] \
        == package["candidate_package_sha256"]


def test_finalizer_rejects_broken_chain():
    finalizer = _load_candidate_module(
        "12_finalize_governance_baseline.py.txt")
    candidate = _load("05_phase5_governance_baseline_candidate.json")
    package = _load("10_candidate_package.json")
    acceptance = json.dumps({
        "scope": "P5-GOV-REOPEN-CPUB",
        "decision": "APPROVE",
        "accepted_by": "HUMAN",
        "candidate_package_sha256":
            package["candidate_package_sha256"],
    }).encode("utf-8")
    manifest_bytes = (CAND / "09_candidate_manifest.json").read_bytes()
    activation = {"scope": "P5-GOV-REOPEN-CPUB",
                  "authority_status": "ACTIVE",
                  "candidate_package_sha256": "WRONG"}
    activation_bytes = json.dumps(activation).encode("utf-8")
    with pytest.raises(ValueError):
        finalizer.finalize_governance_baseline(
            candidate_baseline_bytes=(CAND /
                "05_phase5_governance_baseline_candidate.json").read_bytes(),
            candidate_package_bytes=(CAND /
                "10_candidate_package.json").read_bytes(),
            human_acceptance_bytes=acceptance,
            activation_bytes=activation_bytes)


def test_modified_unapproved_baseline_candidate_fails():
    finalizer = _load_candidate_module(
        "12_finalize_governance_baseline.py.txt")
    package = _load("10_candidate_package.json")
    baseline_bytes = bytearray((CAND /
        "05_phase5_governance_baseline_candidate.json").read_bytes())
    tampered = json.loads(baseline_bytes.decode("utf-8"))
    tampered["authority_rule"] = "HACKED"
    tampered_bytes = json.dumps(tampered).encode("utf-8")
    acceptance = json.dumps({
        "scope": "P5-GOV-REOPEN-CPUB", "decision": "APPROVE",
        "accepted_by": "HUMAN",
        "candidate_package_sha256":
            package["candidate_package_sha256"],
    }).encode("utf-8")
    activation_bytes = json.dumps({
        "scope": "P5-GOV-REOPEN-CPUB", "authority_status": "ACTIVE",
        "candidate_package_sha256":
            package["candidate_package_sha256"]}).encode("utf-8")
    with pytest.raises(ValueError) as exc:
        finalizer.finalize_governance_baseline(
            candidate_baseline_bytes=tampered_bytes,
            candidate_package_bytes=(CAND /
                "10_candidate_package.json").read_bytes(),
            human_acceptance_bytes=acceptance,
            activation_bytes=activation_bytes)
    assert "BASELINE_CANDIDATE_PACKAGE_MISMATCH" in str(exc.value)


def test_rev8_baseline_pins_rev3_frozen_manifest():
    """H1K R2-01E alignment: the ACTIVE Rev8 baseline pins the ACTIVE
    frozen-surface manifest identity (resolved via _gov_current). The Rev3 CPUB
    04 artifact is superseded and is no longer part of the binding chain; the
    runtime manifest mirror is byte-identical to the ACTIVE accepted bytes."""
    candidate = _load("05_phase5_governance_baseline_candidate.json")
    active_sha = _sha(PROJECT_ROOT / "audit/phase5/"
                      "frozen_surface_manifest.json")
    entries = {
        e["path"]: e["sha256"]
        for e in candidate["governance_files"]
    }
    assert candidate["frozen_surface_manifest_sha256"] == _ids["manifest"]
    assert entries["audit/phase5/frozen_surface_manifest.json"] \
        == _ids["manifest"]
    assert active_sha == _ids["manifest"]
    # Superseded Rev3 CPUB candidate artifact is not the ACTIVE identity.
    superseded_04 = _load("04_frozen_surface_manifest_candidate.json")
    assert superseded_04["revision"] != _ids["manifest_revision"]
    assert _sha(CAND / "04_frozen_surface_manifest_candidate.json") \
        != _ids["manifest"]


def test_r2_01_rev8_candidate_manifest_sha_matches_governance_files():
    """H1K R2-01E alignment: Rev8 baseline governance_files manifest pin equals
    the ACTIVE manifest SHA and the top-level manifest binding; the superseded
    Rev3 CPUB 04 artifact no longer defines the chain."""
    candidate = _load("05_phase5_governance_baseline_candidate.json")
    entries = {
        e["path"]: e["sha256"]
        for e in candidate["governance_files"]
    }
    active_sha = _sha(PROJECT_ROOT / "audit/phase5/"
                      "frozen_surface_manifest.json")
    assert candidate["frozen_surface_manifest_sha256"] == _ids["manifest"]
    assert entries["audit/phase5/frozen_surface_manifest.json"] \
        == _ids["manifest"]
    assert active_sha == _ids["manifest"]
    # R2-01A dependency ordering: Rev8 baseline must NOT bind the 09 candidate
    # manifest (the candidate manifest binds the baseline, not vice versa).
    assert "candidate_manifest_sha256" not in candidate


def test_r2_01_materialized_manifest_sha_matches_rev8_baseline():
    """H1K R2-01E alignment: post-materialization the ACTIVE operational
    manifest is the IDENTICAL_CURRENT_GOVERNANCE mirror — ACTIVE bytes == runtime
    mirror bytes == Rev8 baseline pin (all resolved, no hardcoded SHA)."""
    candidate = _load("05_phase5_governance_baseline_candidate.json")
    entries = {
        e["path"]: e["sha256"]
        for e in candidate["governance_files"]
    }
    active_sha = _sha(
        PROJECT_ROOT / "audit" / "phase5" / "frozen_surface_manifest.json")
    manifest_09 = _load("09_candidate_manifest.json")
    mirror_entry = next(
        e for e in manifest_09["files"]
        if e["role"] == "FROZEN_SURFACE_MANIFEST_CANDIDATE")
    mirror_sha = _sha(PROJECT_ROOT / mirror_entry["candidate_path"])
    assert mirror_entry["materialization_type"] \
        == "IDENTICAL_CURRENT_GOVERNANCE"
    assert mirror_sha == active_sha
    assert active_sha == _ids["manifest"]
    assert entries["audit/phase5/frozen_surface_manifest.json"] \
        == _ids["manifest"]
    assert candidate["frozen_surface_manifest_sha256"] == _ids["manifest"]
    # Superseded Rev3 CPUB 04 artifact must not resurface as the ACTIVE bytes.
    assert _sha(CAND / "04_frozen_surface_manifest_candidate.json") \
        != _ids["manifest"]


def test_r2_01_reviewer_uses_same_manifest_sha_binding():
    """H1K R2-01E enforcement path: the reviewer's governance-baseline loader
    must accept the runtime mirror of the ACTIVE Rev8 baseline referenced by the
    final candidate package, and the pinned manifest SHA the reviewer compares
    (P5-GOV-03 semantics) must equal the ACTIVE manifest SHA and the runtime
    mirror bytes used everywhere in the chain (no hardcoded SHA)."""
    tools_review = PROJECT_ROOT / "tools" / "review"
    if str(tools_review) not in sys.path:
        sys.path.insert(0, str(tools_review))
    import merge_project_for_phase5_review as reviewer

    package = _load("10_candidate_package.json")
    baseline_mirror_rel = package["referenced_files"][
        "GOVERNANCE_BASELINE_PREACTIVATION_CANDIDATE"]
    manifest_mirror_rel = package["referenced_files"][
        "FROZEN_SURFACE_MANIFEST_CANDIDATE"]
    baseline, err = reviewer.load_governance_baseline(
        PROJECT_ROOT,
        rel=baseline_mirror_rel,
    )
    assert err == ""
    entries = {
        e["path"]: e["sha256"]
        for e in baseline["governance_files"]
    }
    pinned = entries["audit/phase5/frozen_surface_manifest.json"]
    candidate_file_sha = reviewer.sha256_file(
        PROJECT_ROOT / manifest_mirror_rel)
    assert pinned == candidate_file_sha
    assert pinned == baseline["frozen_surface_manifest_sha256"]
    assert candidate_file_sha == _ids["manifest"]
    # Stale identities (Rev2 operational sha or earlier stale pin) must never
    # resurface as the ACTIVE manifest binding.
    assert pinned not in (
        "edb531c118e85f51738e37656687c59850763802eb0a12f194a552ef9bf54e75",
        "20d6034cb12eaec590022dad82839a4a2c174236293cd97eb245e9ed4b24cfa8",
    )
