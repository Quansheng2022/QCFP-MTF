# coding: utf-8
"""Phase 3 — Canonical Decision Chain Closure 专项测试（PHASE3-V1.1）

覆盖 F01-F07 与对抗矩阵 A21-A29。
"""

import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))


# ---------------------------------------------------------------------------
# F01 — Actual Runtime Chain Binding
# ---------------------------------------------------------------------------

def test_actual_runtime_call_order_conforms():
    from QCFP_MTF.governance.phase3 import chain_conformance_evidence
    ev = chain_conformance_evidence()
    assert ev["runtime_source"] == "OBSERVED_CALL_TRACE"
    assert ev["status"] == "PASS"
    assert ev["verdict"] == "CHAIN_CONFORMANT", ev
    assert ev["observed_canonical_stage_path"] == \
        ["INPUT", "PERMISSION", "OPPORTUNITY", "LIFECYCLE", "GOVERNANCE"]


def test_snapshot_path_matches_observed_runtime():
    from QCFP_MTF.governance.phase3 import chain_conformance_evidence
    ev = chain_conformance_evidence()
    assert ev["runtime_snapshot_match"] is True
    assert ev["observed_canonical_stage_path"] == \
        ev["snapshot_canonical_stage_path"]
    assert ev["canonical_stage_path"] == \
        ["INPUT", "PERMISSION", "OPPORTUNITY", "LIFECYCLE", "GOVERNANCE",
         "OUTPUT", "FACT", "VALIDATION"]
    assert ev["missing_stages"] == []
    assert ev["reverse_edges"] == []


def test_real_runtime_chain_reorder_detected():   # A21
    from QCFP_MTF.governance.phase3 import chain_conformance_evidence
    ev = chain_conformance_evidence(
        observed_runtime_path=[
            "evidence", "institutional", "exit_events", "setup",
            "participation_budget", "trade_quality",   # GOVERNANCE 提前
            "fsm", "sizing", "wave", "final_target"],
        snapshot_path=[
            "evidence", "institutional", "exit_events", "setup",
            "participation_budget", "fsm", "sizing", "permission_cap",
            "trade_quality", "governance", "final_target"])
    assert ev["status"] == "FAIL"
    assert ev["verdict"] == "CHAIN_NON_CONFORMANT"
    assert ev["reverse_edges"] != []


def test_wave_occurs_before_fsm_in_actual_runtime():   # A30
    """真实 Engine 运行时：wave（OPPORTUNITY）必须先于 fsm（LIFECYCLE）。"""
    from QCFP_MTF.governance.phase3 import _observe_runtime_chain
    observed, snap = _observe_runtime_chain()
    assert "wave" in observed, observed
    assert "fsm" in observed, observed
    assert observed.index("wave") < observed.index("fsm"), observed
    seq = ["setup", "participation_budget", "wave", "fsm", "sizing"]
    idx = [observed.index(t) for t in seq]
    assert idx == sorted(idx), observed
    assert "wave" in snap.decision_path
    assert list(snap.decision_path).index("wave") < \
        list(snap.decision_path).index("fsm")


def test_runtime_trace_exactly_matches_snapshot_path():   # A31
    """normalized observed runtime tokens == DecisionSnapshot.decision_path；
    wave/governance 缺失必须被真实发现（token 级比对，不再只比 stage）。"""
    from QCFP_MTF.governance.phase3 import (
        _normalize_observed_runtime_path, _normalize_snapshot_path,
        chain_conformance_evidence)
    ev = chain_conformance_evidence()
    assert ev["runtime_snapshot_match"] is True
    assert ev["status"] == "PASS"
    observed = ev["observed_runtime_path"]
    snapshot = ev["snapshot_declared_path"]
    assert _normalize_observed_runtime_path(observed) == \
        _normalize_snapshot_path(snapshot)
    # wave 缺失 → token mismatch（且不再有 wave 豁免）
    bad = chain_conformance_evidence(
        observed_runtime_path=[t for t in observed if t != "wave"],
        snapshot_path=snapshot)
    assert bad["runtime_snapshot_match"] is False
    assert bad["status"] == "FAIL"
    # governance 缺失 → token mismatch
    bad2 = chain_conformance_evidence(
        observed_runtime_path=observed,
        snapshot_path=[t for t in snapshot if t != "governance"])
    assert bad2["runtime_snapshot_match"] is False
    assert bad2["status"] == "FAIL"


# ---------------------------------------------------------------------------
# F02 — Recursive Canonical Root Audit
# ---------------------------------------------------------------------------

def test_nested_second_canonical_evaluator_detected():   # A22
    from QCFP_MTF.governance.phase3 import recursive_canonical_root_audit
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "decision").mkdir(parents=True)
        (root / "decision" / "engine.py").write_text(
            "def evaluate(x):\n    return {'target_position': 0.1}\n",
            encoding="utf-8")
        (root / "decision" / "legacy").mkdir()
        (root / "decision" / "legacy" / "alternate_engine.py").write_text(
            "def evaluate(x):\n    return {'target_position': 0.8, "
            "'canonical_action': 'ENTRY'}\n",
            encoding="utf-8")
        audit = recursive_canonical_root_audit(root)
        assert audit["pass"] is False
        assert audit["verdict"] == "PATH_NON_CONFORMANT"
        assert len(audit["second_canonical_roots"]) == 1
        assert audit["second_canonical_roots"] == \
            ["decision.legacy.alternate_engine"]
    real = recursive_canonical_root_audit()
    assert real["pass"] is True, real
    assert real["canonical_roots"] == ["decision.engine"]
    assert real["second_canonical_roots"] == []


def test_canonical_path_provider_single_root():
    from QCFP_MTF.governance.phase3 import canonical_path_provider
    prov = canonical_path_provider()
    assert prov["status"] == "PASS", prov
    assert prov["verdict"] == "PATH_CONFORMANT"
    assert prov["evidence"]["canonical_roots"] == 1
    assert prov["evidence"]["report_recompute"] == []
    assert prov["evidence"]["final_target_writers"] == 1
    assert prov["evidence"]["final_target_authority"] == \
        ["decision.governance"]


def test_nested_report_recompute_detected():   # A32
    from QCFP_MTF.governance.phase3 import canonical_path_provider
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "decision").mkdir(parents=True)
        (root / "decision" / "engine.py").write_text(
            "def evaluate(x):\n    return {'target_position': 0.1}\n",
            encoding="utf-8")
        (root / "report" / "nested").mkdir(parents=True)
        (root / "report" / "nested" / "evil.py").write_text(
            "from QCFP_MTF.decision.engine import evaluate\n\n"
            "def render(x):\n    return evaluate(x)\n",
            encoding="utf-8")
        (root / "scripts").mkdir()
        (root / "scripts" / "decision_engine.py").write_text(
            "# projection only\n", encoding="utf-8")
        (root / "governance").mkdir()
        (root / "governance" / "pwc2_authority_graph.py").write_text(
            "STATIC_AUTHORITY = {'decision.governance': 'FINAL_TARGET'}\n",
            encoding="utf-8")
        prov = canonical_path_provider(root)
        assert prov["status"] == "FAIL", prov
        assert prov["verdict"] == "PATH_NON_CONFORMANT"
        files = [r["file"] for r in prov["evidence"]["report_recompute"]]
        assert "report/nested/evil.py" in files


def test_nested_script_recompute_detected():   # A33
    from QCFP_MTF.governance.phase3 import canonical_path_provider
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "decision").mkdir(parents=True)
        (root / "decision" / "engine.py").write_text(
            "def evaluate(x):\n    return {'target_position': 0.1}\n",
            encoding="utf-8")
        (root / "scripts" / "nested").mkdir(parents=True)
        (root / "scripts" / "nested" / "alternate.py").write_text(
            "from QCFP_MTF.decision.engine import evaluate\n\n"
            "def run(x):\n    return evaluate(x)\n",
            encoding="utf-8")
        (root / "report").mkdir()
        (root / "governance").mkdir()
        (root / "governance" / "pwc2_authority_graph.py").write_text(
            "STATIC_AUTHORITY = {'decision.governance': 'FINAL_TARGET'}\n",
            encoding="utf-8")
        prov = canonical_path_provider(root)
        assert prov["status"] == "FAIL", prov
        assert prov["verdict"] == "PATH_NON_CONFORMANT"
        files = [r["file"] for r in prov["evidence"]["script_recompute"]]
        assert "scripts/nested/alternate.py" in files


# ---------------------------------------------------------------------------
# P3.2 — Runtime Invariants
# ---------------------------------------------------------------------------

def test_runtime_invariants_seven():
    from QCFP_MTF.governance.phase3 import runtime_invariants_provider
    prov = runtime_invariants_provider()
    assert prov["status"] == "PASS", prov
    assert prov["verdict"] == "RUNTIME_INVARIANTS_PASS"
    assert len(prov["evidence"]["invariants"]) == 7
    assert prov["evidence"]["failed"] == []


# ---------------------------------------------------------------------------
# P3.3 — Determinism / Identity
# ---------------------------------------------------------------------------

def test_e2e_determinism_exact():
    from QCFP_MTF.governance.phase3 import e2e_determinism_provider
    prov = e2e_determinism_provider()
    assert prov["status"] == "PASS", prov
    assert prov["verdict"] == "DETERMINISTIC"
    assert prov["evidence"]["mismatches"] == []


def test_decision_identity_fail_closed():
    from QCFP_MTF.governance.phase3 import decision_identity_provider
    prov = decision_identity_provider()
    assert prov["status"] == "PASS", prov
    assert prov["evidence"]["checks"]["missing_release_rejected"]["pass"]
    assert prov["evidence"]["checks"][
        "missing_evidence_not_certified"]["pass"]


# ---------------------------------------------------------------------------
# F03 — PathHash Independent Adversarial Proof
# ---------------------------------------------------------------------------

def test_path_hash_identity_stable():
    from QCFP_MTF.governance.phase3 import path_hash_evidence
    ev = path_hash_evidence()
    assert ev["identical_identity_stable"] is True
    assert ev["verdict"] == "PATH_HASH_PASS"


def test_path_hash_critical_mutations_detected():
    from QCFP_MTF.governance.phase3 import path_hash_evidence
    ev = path_hash_evidence()
    assert ev["mutation_failures"] == []
    assert len(ev["mutations"]) >= 8
    for name, result in ev["mutations"].items():
        assert result["pass"] is True, (name, result)
        assert result["expected"] == "HASH_MUST_CHANGE"


def test_same_identity_different_hash_detected():
    from QCFP_MTF.governance.phase3 import path_hash_evidence
    ev = path_hash_evidence()
    assert ev["helper"]["same_identity_diff_hash"] == \
        "DETERMINISM_FAILURE"
    assert ev["helper"]["diff_identity_same_hash"] == "PATH_HASH_DRIFT"


def test_constant_path_hash_detected():   # A23
    from QCFP_MTF.governance.phase3 import (
        path_hash_evidence, path_hash_evidence_constant_probe,
        path_hash_provider)
    ev = path_hash_evidence(hash_fn=lambda *_a, **_k: "CONSTANT")
    assert ev["verdict"] == "PATH_HASH_FAIL"
    assert ev["mutation_failures"]
    assert path_hash_evidence_constant_probe()["blocked"] is True
    assert path_hash_provider()["status"] == "PASS"


# ---------------------------------------------------------------------------
# P3.4 — Ledger / Replay / Report
# ---------------------------------------------------------------------------

def test_ledger_append_only_evidence():
    from QCFP_MTF.governance.phase3 import ledger_provider
    prov = ledger_provider()
    assert prov["status"] == "PASS", prov
    checks = prov["evidence"]["checks"]
    assert checks["append_only"] is True
    assert checks["no_update"] is True
    assert checks["no_delete"] is True
    assert checks["chain_tamper_detected"] is True


def test_replay_exactness():
    from QCFP_MTF.governance.phase3 import replay_provider
    prov = replay_provider()
    assert prov["status"] == "PASS", prov
    checks = prov["evidence"]["checks"]
    assert checks["exact_replay"]["pass"]
    assert checks["tamper_detected"]["pass"]
    assert checks["mismatch_fail_closed"]["pass"]


def test_report_projection_no_recompute():
    from QCFP_MTF.governance.phase3 import report_projection_provider
    prov = report_projection_provider()
    assert prov["status"] == "PASS", prov
    checks = prov["evidence"]["checks"]
    assert checks["report_equals_ledger"]["ok"] is True
    assert checks["report_rewrite_rejected"]["ok"] is True
    assert checks["adapter_no_recompute"]["forbidden_imports"] == []


# ---------------------------------------------------------------------------
# P3.5 — Golden / Failure Injection
# ---------------------------------------------------------------------------

def test_golden_corpus_14_cases():
    from QCFP_MTF.governance.phase3 import golden_provider
    prov = golden_provider()
    assert prov["status"] == "PASS", prov
    assert prov["evidence"]["n_cases"] == 14
    assert prov["evidence"]["n_failed"] == 0
    assert prov["evidence"]["failed_cases"] == []
    assert prov["evidence"]["coverage"]["ok"] is True
    assert prov["evidence"]["hash_change_requires_review"] is True
    assert prov["evidence"]["unexplained_change_blocked"] is True


def test_failure_injection_qualified():
    from QCFP_MTF.governance.phase3 import failure_injection_provider
    prov = failure_injection_provider()
    assert prov["status"] == "PASS", prov
    assert prov["evidence"]["verdict"] == "RELEASE_QUALIFIED"
    assert prov["evidence"]["failure_escaped_count"] == 0
    assert prov["evidence"]["missing_cases"] == []


# ---------------------------------------------------------------------------
# F04 — Frozen Baseline Binding
# ---------------------------------------------------------------------------

def test_frozen_baseline_provider_real_pass():
    from QCFP_MTF.governance.phase3 import frozen_baseline_provider
    prov = frozen_baseline_provider()
    assert prov["status"] == "PASS", prov
    assert prov["verdict"] == "BASELINE_PASS"


def test_phase3_fails_on_baseline_drift(monkeypatch):   # A24
    from QCFP_MTF.governance import governance_baseline as gb
    from QCFP_MTF.governance.phase3 import frozen_baseline_provider
    real = gb.load_baseline()
    drifted = dict(real)
    drifted["architecture_hash"] = "deadbeef"
    monkeypatch.setattr(gb, "load_baseline", lambda: drifted)
    prov = frozen_baseline_provider()
    assert prov["status"] == "FAIL"
    assert prov["verdict"] == "BASELINE_CHANGED"
    # 磁盘上的 Frozen Baseline 未被篡改（monkeypatch 只影响测试内调用）
    on_disk = json.loads(
        (gb.default_baseline_dir() / gb.BASELINE_FILENAME)
        .read_text(encoding="utf-8"))
    assert on_disk["architecture_hash"] != "deadbeef"


# ---------------------------------------------------------------------------
# F05/F06 — Independent Regression Evidence + Tri-State
# ---------------------------------------------------------------------------

def _regression_provider_with(evidence_path):
    from QCFP_MTF.governance.phase3 import regression_provider
    return lambda: regression_provider(evidence_path=evidence_path)


def _all_providers_except(name, replacement):
    from QCFP_MTF.governance import phase3
    out = []
    for n, pri, fn in phase3.PHASE3_GATES:
        if n == name:
            out.append((n, pri, replacement))
        else:
            out.append((n, pri, fn))
    return out


def test_missing_regression_evidence_not_proven(tmp_path):   # A25
    from QCFP_MTF.governance.phase3 import (
        EvidenceUnavailable, phase3_acceptance, regression_provider)
    missing = tmp_path / "no_such_summary.json"
    try:
        regression_provider(evidence_path=missing)
        raise AssertionError("should raise EvidenceUnavailable")
    except EvidenceUnavailable:
        pass
    acc = phase3_acceptance(
        tmp_path / "out",
        providers=_all_providers_except(
            "REGRESSION", _regression_provider_with(missing)))
    assert acc["verdict"] == "PHASE3_NOT_PROVEN"
    assert "REGRESSION" in acc["missing_evidence"]


def test_evidence_unavailable_not_proven(tmp_path):   # A26
    from QCFP_MTF.governance.phase3 import EvidenceUnavailable, \
        phase3_acceptance

    def unavailable():
        raise EvidenceUnavailable("db unavailable")
    # REGRESSION 一并隔离：本测试只验证 CHAIN_CONFORMANCE 证据缺失 → NOT_PROVEN，
    # 不依赖 ambient audit/phase3 回归证据状态（否则真实 FAIL 证据会污染结果）。
    providers = _all_providers_except("CHAIN_CONFORMANCE", unavailable)
    providers = [
        (n, p, unavailable if n == "REGRESSION" else fn)
        for n, p, fn in providers]
    acc = phase3_acceptance(
        tmp_path / "out",
        providers=providers)
    assert acc["verdict"] == "PHASE3_NOT_PROVEN"
    assert "CHAIN_CONFORMANCE" in acc["missing_evidence"]


def test_regression_failure_phase3_fail(tmp_path):   # A27
    from QCFP_MTF.governance.phase3 import phase3_acceptance, \
        regression_provider
    ev = tmp_path / "phase3_regression_summary.json"
    ev.write_text(json.dumps({
        "required_suites": ["phase3", "decision", "governance", "full_core"],
        "suites": {
            "phase3": {"status": "PASS", "collected": 10, "passed": 10,
                       "failed": 0, "errors": 0, "skipped": 0},
            "decision": {"status": "FAIL", "collected": 10, "passed": 9,
                         "failed": 1, "errors": 0, "skipped": 0,
                         "failures_detail": [
                             {"test": "x", "message": "assert",
                              "classification": "ASSERTION_FAILURE"}]},
            "governance": {"status": "PASS", "collected": 10, "passed": 10,
                           "failed": 0, "errors": 0, "skipped": 0},
            "full_core": {"status": "PASS", "collected": 10, "passed": 10,
                          "failed": 0, "errors": 0, "skipped": 0}}}),
        encoding="utf-8")
    prov = regression_provider(evidence_path=ev)
    assert prov["status"] == "FAIL"
    acc = phase3_acceptance(
        tmp_path / "out",
        providers=_all_providers_except(
            "REGRESSION", _regression_provider_with(ev)))
    assert acc["verdict"] == "PHASE3_FAIL"
    assert "REGRESSION" in acc["failures"]


def _write_regression(tmp_path, suites, verdict="PASS"):
    ev = tmp_path / "phase3_regression_summary.json"
    ev.write_text(json.dumps({
        "required_suites": ["phase3", "decision", "governance", "full_core"],
        "suites": suites, "verdict": verdict}), encoding="utf-8")
    return ev


def _pass_suite(passed=10, skipped=0):
    return {"status": "PASS", "collected": passed + skipped,
            "passed": passed, "failed": 0, "errors": 0,
            "skipped": skipped, "failures": []}


def test_regression_requires_all_required_suites(tmp_path):   # A34
    from QCFP_MTF.governance.phase3 import regression_provider
    ev = _write_regression(tmp_path, {"phase3": _pass_suite()})
    prov = regression_provider(evidence_path=ev)
    assert prov["status"] == "NOT_PROVEN", prov
    assert prov["verdict"] == "REGRESSION_NOT_PROVEN"
    assert prov["evidence"]["missing_suites"] == \
        ["decision", "full_core", "governance"]


def test_regression_rejects_contradictory_pass_counts(tmp_path):   # A35
    from QCFP_MTF.governance.phase3 import regression_provider
    suites = {k: _pass_suite() for k in
              ("phase3", "decision", "governance", "full_core")}
    suites["decision"]["failed"] = 10
    suites["decision"]["collected"] = 20
    ev = _write_regression(tmp_path, suites)
    prov = regression_provider(evidence_path=ev)
    assert prov["status"] == "FAIL", prov
    assert prov["verdict"] == "REGRESSION_EVIDENCE_INVALID"
    assert "status=PASS 但 failed/errors > 0" in prov["problems"][0]


def test_required_skip_is_not_proven(tmp_path):   # A36 (provider)
    from QCFP_MTF.governance.phase3 import regression_provider
    suites = {k: _pass_suite() for k in
              ("phase3", "decision", "governance", "full_core")}
    suites["decision"] = _pass_suite(passed=9, skipped=1)
    ev = _write_regression(tmp_path, suites)
    prov = regression_provider(evidence_path=ev)
    assert prov["status"] == "NOT_PROVEN", prov
    assert prov["verdict"] == "REGRESSION_NOT_PROVEN"
    assert any("skipped" in str(p) for p in prov["problems"])


def test_mixed_environment_and_assertion_is_fail(tmp_path):   # A37
    from QCFP_MTF.governance.phase3 import regression_provider
    suites = {k: _pass_suite() for k in
              ("phase3", "decision", "governance", "full_core")}
    suites["decision"] = {
        "status": "ENVIRONMENT_BLOCKED", "collected": 2, "passed": 0,
        "failed": 2, "errors": 0, "skipped": 0,
        "failures": [
            {"test": "A", "message": "OperationalError: no such table",
             "classification": "ENVIRONMENT_BLOCKED"},
            {"test": "B", "message": "AssertionError: assert 1 == 2",
             "classification": "ASSERTION_FAILURE"}]}
    ev = _write_regression(tmp_path, suites)
    prov = regression_provider(evidence_path=ev)
    assert prov["status"] == "FAIL", prov
    assert prov["verdict"] == "REGRESSION_EVIDENCE_INVALID"


def test_pure_environment_failure_is_not_proven(tmp_path):   # A38
    from QCFP_MTF.governance.phase3 import regression_provider
    suites = {k: _pass_suite() for k in
              ("phase3", "decision", "governance", "full_core")}
    suites["decision"] = {
        "status": "ENVIRONMENT_BLOCKED", "collected": 2, "passed": 0,
        "failed": 2, "errors": 0, "skipped": 0,
        "failures": [
            {"test": "A", "message": "OperationalError: no such table",
             "classification": "ENVIRONMENT_BLOCKED"},
            {"test": "B", "message": "database is locked",
             "classification": "ENVIRONMENT_BLOCKED"}]}
    ev = _write_regression(tmp_path, suites)
    prov = regression_provider(evidence_path=ev)
    assert prov["status"] == "NOT_PROVEN", prov
    assert prov["verdict"] == "REGRESSION_NOT_PROVEN"


# ---------------------------------------------------------------------------
# F07 — Derived Freeze Record
# ---------------------------------------------------------------------------

def _pass_gates():
    from QCFP_MTF.governance import phase3
    return {n: {"status": "PASS", "evidence": {}}
            for n, _p, _f in phase3.PHASE3_GATES}


def test_freeze_bypass_count_is_derived():   # A28
    from QCFP_MTF.governance.phase3 import derive_freeze_record
    gates = _pass_gates()
    gates["FAILURE_INJECTION"]["evidence"] = {"failure_escaped_count": 1}
    rec = derive_freeze_record(gates, [])
    assert rec["known_decision_bypass"] == 1
    assert rec["open_p0"] == 0


def test_freeze_second_root_count_is_derived():   # A29
    from QCFP_MTF.governance.phase3 import derive_freeze_record
    gates = _pass_gates()
    gates["CANONICAL_PATH"]["evidence"] = {
        "second_canonical_roots": ["a.evaluate", "b.evaluate"]}
    rec = derive_freeze_record(gates, [])
    assert rec["second_canonical_path"] == 2


# ---------------------------------------------------------------------------
# Acceptance Pack（REGRESSION 由独立 Test System 证据支撑）
# ---------------------------------------------------------------------------

def test_phase3_acceptance_pack(tmp_path):
    from QCFP_MTF.governance import phase3
    ev = tmp_path / "phase3_regression_summary.json"
    ev.write_text(json.dumps({
        "suites": {k: {"status": "PASS", "collected": 1, "passed": 1,
                       "failed": 0, "errors": 0}
                   for k in ("phase3", "decision", "governance",
                             "full_core")},
        "verdict": "PASS"}), encoding="utf-8")
    out = tmp_path / "phase3"
    acc = phase3.phase3_acceptance(
        out,
        providers=_all_providers_except(
            "REGRESSION", _regression_provider_with(ev)))
    assert acc["verdict"] == "PHASE3_PASS", acc
    assert acc["failures"] == []
    assert acc["missing_evidence"] == []
    assert acc["freeze_state"] == "FREEZE_CANDIDATE"
    assert (out / "phase3_acceptance.json").exists()
    assert (out / "canonical_chain_map.json").exists()
    assert (out / "golden_result.json").exists()
    assert (out / "freeze_record.txt").exists()
    data = json.loads((out / "phase3_acceptance.json")
                      .read_text(encoding="utf-8"))
    assert data["verdict"] == "PHASE3_PASS"
