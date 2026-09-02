# coding: utf-8
"""Acceptance / Test Contract（流程治理 Sprint B #5 + FGC-1 C3）

Acceptance/Test Contract **左移到编码之前**：
    Change Request → Acceptance Contract → Tests / Expected Behaviour Frozen
    → Implementation

C3 升级为 Frozen Test Oracle：
    * 每个 Case 固定结构：case_id / spec_ids / input_fixture{fixture_id,
      input_hash} / expected{...result_hash}
    * 执行结果：case_id / input_hash / expected_hash / actual_hash / pass
    * Gate 必须检查：Case IDs 一致、数量一致、Input Hash 一致、
      Expected Hash 一致、Actual == Expected
    任一缺失 → EVIDENCE_GAP；任一不一致 → ACCEPTANCE_FAIL

Decision Delta 正式进入 Gate：max_changed_decisions / allowed_fields /
forbidden_fields / expected_direction 必须与实际 decision_deltas 比对。

Builder 默认禁止修改 Frozen Golden / Test Oracle；Oracle 变更必须携带
oracle_change_adr_hash / human_approval_id / previous_oracle_hash /
new_oracle_hash / reason，否则 ORACLE_CHANGE_REJECTED。
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from .traceability import load_yaml_file


CONTRACT_PATH = Path(__file__).resolve().parent / "acceptance_contract.yaml"

REQUIRED_SECTIONS = (
    "spec_requirements", "positive_cases", "boundary_cases",
    "negative_cases", "adversarial_cases", "golden_cases",
    "expected_invariant_results", "expected_decision_deltas",
    "expected_unchanged_cases",
)

CRITICAL_CASE_KINDS = ("positive_cases", "negative_cases",
                       "boundary_cases", "adversarial_cases")


def load_contract(path=None) -> dict:
    data = load_yaml_file(path or CONTRACT_PATH)
    return data if isinstance(data, dict) else {}


def _case_errors(case: dict, index: int, kind: str) -> list:
    errors = []
    if not case.get("case_id"):
        errors.append(f"{kind}[{index}]: missing case_id")
    fixture = case.get("input_fixture") or {}
    if not fixture.get("input_hash"):
        errors.append(f"{kind}[{index}]: missing input_fixture.input_hash")
    expected = case.get("expected") or {}
    if not expected.get("result_hash"):
        errors.append(f"{kind}[{index}]: missing expected.result_hash")
    return errors


def validate_acceptance_contract(contract: dict,
                                 critical_change: bool = False) -> dict:
    """Contract 完整性 + Case 结构校验。critical_change 四类用例缺任一 → 无效。"""
    errors = []
    for section in REQUIRED_SECTIONS:
        value = contract.get(section)
        if section == "spec_requirements":
            missing = not isinstance(value, list) or not value
        elif value is None or value == "":
            missing = True
        else:
            missing = False
        if missing:
            errors.append(f"missing required section: {section}")
    for kind in CRITICAL_CASE_KINDS:
        for i, case in enumerate(contract.get(kind) or []):
            errors.extend(_case_errors(case, i, kind))
    for i, case in enumerate(contract.get("golden_cases") or []):
        errors.extend(_case_errors(case, i, "golden_cases"))
    if critical_change:
        for kind in CRITICAL_CASE_KINDS:
            if not contract.get(kind):
                errors.append(f"critical change requires cases: {kind}")
    oracle = contract.get("test_oracle_change") or {}
    if oracle.get("required"):
        for field in ("oracle_change_adr_hash", "human_approval_id",
                      "previous_oracle_hash", "new_oracle_hash", "reason"):
            if not oracle.get(field):
                errors.append(f"test oracle change requires {field}")
    frozen_golden = contract.get("frozen_golden_expected", True)
    if not frozen_golden and not oracle.get("human_approval_id"):
        errors.append("frozen golden expected disabled without human approval")
    return {
        "change_id": contract.get("change_id"),
        "errors": errors,
        "valid": not errors,
        "verdict": "ACCEPTANCE_CONTRACT_VALID" if not errors
        else "ACCEPTANCE_CONTRACT_INVALID",
        "critical_change": critical_change,
    }


def _compare_case_set(frozen_cases: list, actual_results: list,
                      kind: str) -> list:
    """Case 级比对：IDs、数量、Input Hash、Expected Hash、Actual==Expected。"""
    failures = []
    frozen_ids = [c.get("case_id") for c in frozen_cases]
    actual = {r.get("case_id"): r for r in (actual_results or [])}
    if set(frozen_ids) != set(actual):
        missing = sorted(set(frozen_ids) - set(actual))
        extra = sorted(set(actual) - set(frozen_ids))
        failures.append(f"{kind}: case_id 不一致 "
                        f"(missing={missing}, extra={extra})")
        return failures
    for case in frozen_cases:
        cid = case.get("case_id")
        result = actual.get(cid) or {}
        frozen_input = (case.get("input_fixture") or {}).get("input_hash")
        frozen_expected = (case.get("expected") or {}).get("result_hash")
        if result.get("input_hash") != frozen_input:
            failures.append(f"{kind}:{cid} input_hash changed")
        if result.get("expected_hash") != frozen_expected:
            failures.append(f"{kind}:{cid} expected_hash changed")
        if result.get("actual_hash") != frozen_expected:
            failures.append(f"{kind}:{cid} actual != expected")
        if result.get("pass") is not True:
            failures.append(f"{kind}:{cid} not passed")
    return failures


def _compare_decision_deltas(frozen: dict, actual: dict) -> list:
    """Decision Delta 正式比对（C3 + P1：配置即强制）。

    max_changed_decisions / allowed_fields / forbidden_fields /
    expected_direction 任一配置 → 对应 actual 字段必填，否则 EVIDENCE_GAP。
    """
    failures, gaps = [], []
    frozen = frozen or {}
    actual = actual or {}
    max_changed = frozen.get("max_changed_decisions")
    changed = actual.get("changed_decisions")
    if max_changed is not None:
        if changed is None:
            gaps.append("changed_decisions missing")
        elif int(changed) > int(max_changed):
            failures.append(
                f"decision delta too large: {changed} > {max_changed}")
    allowed = frozen.get("allowed_fields") or []
    forbidden = frozen.get("forbidden_fields") or []
    if allowed or forbidden:
        if actual.get("changed_fields") is None:
            gaps.append("changed_fields missing")
        else:
            changed_fields = set(actual.get("changed_fields"))
            if allowed and not changed_fields.issubset(set(allowed)):
                failures.append(
                    f"changed fields outside allowed: "
                    f"{sorted(changed_fields - set(allowed))}")
            overlap = sorted(changed_fields & set(forbidden))
            if overlap:
                failures.append(f"changed forbidden fields: {overlap}")
    direction = frozen.get("expected_direction") or {}
    if direction:
        if actual.get("direction_checks") is None:
            gaps.append("direction_checks missing")
        else:
            direction_checks = actual.get("direction_checks") or {}
            for field, expectation in direction.items():
                got = direction_checks.get(field)
                if got is None:
                    failures.append(f"missing direction check: {field}")
                elif expectation == "non_increasing" and got is not True:
                    failures.append(f"{field} not non_increasing")
                elif expectation == "unchanged" and got is not True:
                    failures.append(f"{field} not unchanged")
    return {"failures": failures, "gaps": gaps}


def acceptance_gate(contract: dict, results: dict,
                    critical_change: bool = False) -> dict:
    """Frozen Test Oracle 比对。

    results: {
        "positive_cases": [{case_id, input_hash, expected_hash,
                            actual_hash, pass}...],
        ...,
        "golden": {"results": [...], "n_total":, "n_failed":, "status":},
        "invariants": [ok...],
        "unchanged": [ok...],
        "decision_deltas": {"changed_decisions":, "changed_fields":,
                            "direction_checks": {...}},
    }
    """
    validation = validate_acceptance_contract(contract, critical_change)
    if not validation["valid"]:
        return {"gate": "ACCEPTANCE_GATE",
                "verdict": "ACCEPTANCE_CONTRACT_INVALID",
                "pass": False,
                "errors": validation["errors"]}
    results = results or {}
    failures, gaps = [], []
    for kind in CRITICAL_CASE_KINDS:
        frozen_cases = contract.get(kind) or []
        actual = results.get(kind)
        if not frozen_cases:
            continue
        if actual is None:
            gaps.append(kind)
        else:
            failures.extend(_compare_case_set(frozen_cases, actual, kind))
    golden = results.get("golden") or {}
    golden_cases = contract.get("golden_cases") or []
    golden_results = golden.get("results")
    if golden_cases and golden_results is None:
        gaps.append("golden_cases")
    elif golden_cases:
        failures.extend(
            _compare_case_set(golden_cases, golden_results, "golden_cases"))
    if not golden:
        gaps.append("golden")
    elif not (golden.get("n_total") is not None
              and int(golden.get("n_total")) > 0
              and golden.get("n_failed") is not None
              and int(golden.get("n_failed")) == 0
              and golden.get("status") == "PASS"):
        failures.append("golden")
    invariants = results.get("invariants")
    if invariants is None:
        gaps.append("invariants")
    elif not all(bool(x) for x in invariants):
        failures.append("invariants")
    unchanged = results.get("unchanged")
    if unchanged is None:
        gaps.append("unchanged")
    elif not all(bool(x) for x in unchanged):
        failures.append("unchanged")
    delta = _compare_decision_deltas(
        contract.get("expected_decision_deltas"),
        results.get("decision_deltas"))
    failures.extend(delta["failures"])
    gaps.extend(delta["gaps"])
    oracle = contract.get("test_oracle_change") or {}
    if oracle.get("required") and not oracle.get("human_approval_id"):
        failures.append("oracle change without human approval")
    if failures:
        verdict = "ACCEPTANCE_FAIL"
    elif gaps:
        verdict = "EVIDENCE_GAP"
    else:
        verdict = "ACCEPTANCE_PASS"
    return {
        "gate": "ACCEPTANCE_GATE",
        "schema": "ACCEPTANCE-RESULT-2",
        "change_id": contract.get("change_id"),
        "failures": failures,
        "evidence_gaps": gaps,
        "verdict": verdict,
        "pass": verdict == "ACCEPTANCE_PASS",
        "rule": "Expected Case IDs == Actual Case IDs；Input Hash 冻结；"
                "Expected Hash 冻结；Actual == Expected；任一不一致 → "
                "ACCEPTANCE_FAIL；缺失 → EVIDENCE_GAP",
    }


def acceptance_result_artifact(contract: dict, gate_result: dict,
                               out_dir) -> dict:
    """写 acceptance_result.json（C7 必需 artifact）。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "schema": "ACCEPTANCE-RESULT-2",
        "change_id": contract.get("change_id"),
        "verdict": gate_result.get("verdict"),
        "failures": gate_result.get("failures", []),
        "evidence_gaps": gate_result.get("evidence_gaps", []),
        "generated_at": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "pass": gate_result.get("pass", False),
    }
    (out_dir / "acceptance_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8")
    return result
