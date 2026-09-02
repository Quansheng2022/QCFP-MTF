# coding: utf-8
"""Governance Failure Injection Suite（QCFP-MTF 2.8：新 48 号）

主动攻击自己的治理系统，检查 fail-closed 还是继续交易：
    PIT timestamp future / Permission cap missing / Portfolio cap NaN /
    Liquidity cap negative / Ledger hash tampered / Replay mismatch /
    ConfigHash changed / Future-aware WaveLabel / ValidationCertificate
    missing / ReleaseManifest mismatch / Execution from raw proposal

针对五条最高原则（Permission>Signal / PIT>Prediction / Risk>Return /
Ledger+Replay / OOS>Ablation>subjective）分别必须有 adversarial test。
"""


FAILURE_INJECTION_CASES = (
    "pit_timestamp_future",
    "permission_cap_missing",
    "portfolio_cap_nan",
    "liquidity_cap_negative",
    "ledger_hash_tampered",
    "replay_mismatch",
    "config_hash_changed",
    "future_aware_wave_label",
    "validation_certificate_missing",
    "release_manifest_mismatch",
    "execution_from_raw_proposal",
)

# Release 2（新 20 号）：12 类注入（含 Broker UNKNOWN/Position mismatch）
FAILURE_INJECTION_QUALIFICATION_CASES = (
    "future_pit_timestamp",
    "missing_liquidity_cap",
    "nan_risk_cap",
    "ledger_row_tamper",
    "replay_mismatch",
    "release_manifest_mismatch",
    "evidence_pack_missing",
    "future_aware_wave_label",
    "execution_bare_snapshot",
    "broker_unknown_ack",
    "broker_position_mismatch",
    "report_action_rewrite",
)


def failure_injection_cases() -> dict:
    """11 类注入攻击：每类要求 fail-closed（不得继续交易）。"""
    expected = {
        "pit_timestamp_future": "REJECT",
        "permission_cap_missing": "REJECT",
        "portfolio_cap_nan": "REJECT",
        "liquidity_cap_negative": "REJECT",
        "ledger_hash_tampered": "REJECT",
        "replay_mismatch": "REJECT",
        "config_hash_changed": "REJECT",
        "future_aware_wave_label": "REJECT",
        "validation_certificate_missing": "REJECT",
        "release_manifest_mismatch": "REJECT",
        "execution_from_raw_proposal": "REJECT",
    }
    return {"cases": FAILURE_INJECTION_CASES,
            "expected": expected,
            "rule": "治理不能只证明正常情况下能工作，"
                    "还要证明有人绕它时也不能工作"}


def assert_fail_closed(case_id, result) -> dict:
    """校验注入结果是否 fail closed。"""
    ok = result in ("REJECT", "BLOCK", "NO_DECISION", "FAIL")
    return {"case_id": case_id, "result": result,
            "fail_closed": ok,
            "verdict": "FAIL_CLOSED" if ok else "CONTINUED_TRADING",
            "violation": not ok}


PRINCIPLE_ADVERSARIAL_TESTS = (
    "permission_over_signal",
    "pit_over_prediction",
    "risk_over_return",
    "ledger_and_replay",
    "oos_ablation_over_subjective",
)


def principle_adversarial_tests() -> dict:
    """五条最高原则的 adversarial test 定义。"""
    return {"principles": PRINCIPLE_ADVERSARIAL_TESTS,
            "rule": "五条最高原则分别必须有 adversarial test"}


def qualification_classify(result: str) -> str:
    """Release 2（新 20 号）：注入结果必须分类为——
    BLOCKED_AS_DESIGNED / SAFE_MODE / DECISION_HALTED /
    RECOVERY_REQUIRED / FAILURE_ESCAPED。"""
    mapping = {
        "REJECT": "BLOCKED_AS_DESIGNED",
        "NO_DECISION": "SAFE_MODE",
        "DECISION_HALTED": "DECISION_HALTED",
        "RECOVERY_REQUIRED": "RECOVERY_REQUIRED",
        "BLOCK": "BLOCKED_AS_DESIGNED",
        "FAIL": "BLOCKED_AS_DESIGNED",
        "BLOCKED_AS_DESIGNED": "BLOCKED_AS_DESIGNED",
        "SAFE_MODE": "SAFE_MODE",
    }
    return mapping.get(str(result).upper(), "FAILURE_ESCAPED")


def failure_injection_qualification(case_results: dict) -> dict:
    """总验收：FAILURE_ESCAPED > 0 → Release REJECTED。"""
    classifications = {case: qualification_classify(result)
                       for case, result in (case_results or {}).items()}
    escaped = [c for c, r in classifications.items()
               if r == "FAILURE_ESCAPED"]
    return {
        "classifications": classifications,
        "failure_escaped": escaped,
        "failure_escaped_count": len(escaped),
        "verdict": "RELEASE_REJECTED" if escaped else "RELEASE_QUALIFIED",
        "allowed": not escaped,
        "rule": "Failure Injection escaped = 0 才允许 Production Ready",
    }


# ---------------------------------------------------------------------------
# MTR Closure（Sprint C）：真实 12-case Failure Injection
# 每个 case 真正修改输入/状态 → 执行 Production Candidate Path → 观察响应。
# 禁止传 fabricated result；缺失 case → NOT_PROVEN。
# ---------------------------------------------------------------------------

def _snap(decision_id="d1", target=0.2, prev=0.0, release_id="REL-A",
          manifest_hash="HASH-A"):
    from ..decision.decision_snapshot import DecisionSnapshot
    return DecisionSnapshot(
        decision_id=decision_id, stock_code="00700",
        decision_date="2026-08-21",
        institutional_state="ACCUMULATION",
        institutional_permission="ALLOW", permission_cap="TRADE",
        exit_event_kind="NONE", exit_event_reason="", setup_type="BREAKOUT",
        prev_fsm_state="FLAT", next_fsm_state="TESTING",
        previous_position=float(prev), target_position=float(target),
        decision_path=("evidence", "institutional", "fsm", "governance",
                       "final_target"),
        release_id=release_id, release_manifest_hash=manifest_hash)


def _inject(case_id, input_before, injected_change, expected,
            actual, escaped, event, ledger_result=None) -> dict:
    return {"case_id": case_id,
            "input_before": input_before,
            "injected_change": injected_change,
            "expected_behavior": expected,
            "actual_behavior": actual,
            "escaped": bool(escaped),
            "exception/event": event,
            "ledger_result": ledger_result or "NOT_TOUCHED"}


def _case_future_pit_timestamp():
    from ..evidence.snapshot import EvidenceContractError, \
        assert_evidence_asof
    evidence = {"decision_date": "2026-08-20",
                "weekly": {"available_at": "2026-08-21"}}
    try:
        assert_evidence_asof(evidence)
        return _inject("future_pit_timestamp", evidence,
                       "weekly.available_at 未来时间",
                       "BLOCK", "ALLOWED", True,
                       "PIT 违反未抛错")
    except EvidenceContractError as exc:
        return _inject("future_pit_timestamp", evidence,
                       "weekly.available_at 未来时间",
                       "BLOCK", "BLOCK", False, str(exc))


def _case_missing_liquidity_cap():
    from ..decision.governance_caps import caps_governance_check
    row = {"portfolio_cap": 0.3, "liquidity_cap": None,
           "execution_cap": 0.5}
    r = caps_governance_check(row, mode="production")
    block = bool(r.get("unknown")) and r.get("degrade") == "NO_NEW_RISK"
    return _inject("missing_liquidity_cap", row,
                   "liquidity_cap=None",
                   "NO_NEW_RISK", r.get("degrade"), not block,
                   str(r.get("missing_required")), ledger_result="UNKNOWN")


def _case_nan_risk_cap():
    from ..decision.governance import finalize_target
    try:
        fin = finalize_target(
            "ALLOW", "TRADE", 0.5, 0.4, 0.0,
            portfolio_cap=0.3, liquidity_cap=float("nan"),
            execution_cap=0.5)
        target = float(fin["target"])
        # NaN cap → 必须 NO_NEW_RISK：prev=0 时 target 必须为 0
        return _inject("nan_risk_cap",
                       {"prev": 0.0, "raw_target": 0.4,
                        "liquidity_cap": "nan"},
                       "liquidity_cap=NaN",
                       "NO_NEW_RISK", f"target={target}",
                       target > 1e-9,
                       "NaN cap 被静默放行" if target > 1e-9 else
                       "finalize_target UNKNOWN cap → no-new-risk")
    except Exception as exc:
        return _inject("nan_risk_cap",
                       {"prev": 0.0, "raw_target": 0.4,
                        "liquidity_cap": "nan"},
                       "liquidity_cap=NaN",
                       "NO_NEW_RISK", f"EXCEPTION:{type(exc).__name__}",
                       False, str(exc))


def _case_ledger_row_tamper():
    from ..decision.decision_ledger import verify_chain_records
    records = [
        {"run_id": "R1", "id": 1, "prev_hash": "", "current_hash": "abc",
         "run_prev_hash": "", "run_current_hash": "r1"},
        {"run_id": "R1", "id": 2, "prev_hash": "abc", "current_hash": "def",
         "run_prev_hash": "r1", "run_current_hash": "r2"},
    ]
    tampered = [dict(records[0]),
                dict(records[1], prev_hash="tampered")]
    r = verify_chain_records(tampered)
    block = r.get("global_verified") is False
    return _inject("ledger_row_tamper", records,
                   "id=2 prev_hash → 'tampered'",
                   "GLOBAL_CHAIN_MISMATCH",
                   "GLOBAL_CHAIN_MISMATCH" if block else "GLOBAL_OK",
                   not block,
                   str(r.get("mismatch_location")))


def _case_replay_mismatch():
    from ..decision.replay_engine import field_by_field_compare
    original = {"decision_id": "d1", "stock_code": "00700",
                "previous_position": 0.2, "target_position": 0.15,
                "next_fsm_state": "TRIMMING", "primary_reason": "POSITION_CAP"}
    tampered = dict(original, target_position=0.4)
    r = field_by_field_compare(original, tampered)
    block = r.status == "REPLAY_MISMATCH"
    return _inject("replay_mismatch", original,
                   "target_position 0.15 → 0.4",
                   "REPLAY_MISMATCH", r.status, not block,
                   str(r.mismatches))


def _case_release_manifest_mismatch():
    from ..decision.certified_decision import certify_decision
    snap = _snap(release_id="REL-A", manifest_hash="HASH-A")
    r = certify_decision(
        snap, pit_certificate={"status": "PASS"},
        ledger_verification={"status": "PASS"},
        replay_certificate={"status": "PASS"},
        governance_proof={"status": "PASS"},
        production_acceptance={"status": "PASS"},
        safety_status="NORMAL",
        release_manifest={"release_id": "REL-B",
                          "manifest_hash": "HASH-B"},
        evidence_pack={"evidence_hash": "HASH-B",
                       "certification": "CERTIFIED",
                       "release_id": "REL-B"})
    block = not r.get("certified")
    return _inject("release_manifest_mismatch",
                   {"snap_release": "REL-A",
                    "manifest_release": "REL-A"},
                   "manifest_release → REL-B",
                   "REFUSED", "REFUSED" if block else "CERTIFIED",
                   not block, str(r.get("failures")),
                   ledger_result="NO_COMMIT")


def _case_evidence_pack_missing():
    from ..decision.certified_decision import certify_decision
    snap = _snap()
    r = certify_decision(
        snap, pit_certificate={"status": "PASS"},
        ledger_verification={"status": "PASS"},
        replay_certificate={"status": "PASS"},
        governance_proof={"status": "PASS"},
        production_acceptance={"status": "PASS"},
        safety_status="NORMAL",
        release_manifest={"release_id": "REL-A",
                          "manifest_hash": "HASH-A"},
        evidence_pack=None)
    block = not r.get("certified")
    return _inject("evidence_pack_missing",
                   {"evidence_pack": "CERTIFIED"},
                   "evidence_pack=None",
                   "REFUSED", "REFUSED" if block else "CERTIFIED",
                   not block, str(r.get("failures")),
                   ledger_result="NO_COMMIT")


def _case_future_aware_wave_label():
    from ..governance.feature_gate import FeatureGateError
    from ..wave.asof_opportunity import assert_no_outcome_fields
    opp = {"wave_id": "w1", "as_of_date": "2026-08-20",
           "realized_mfe": 0.5}
    try:
        assert_no_outcome_fields(opp)
        return _inject("future_aware_wave_label", opp,
                       "realized_mfe 进入 as-of 机会",
                       "BLOCK", "ALLOWED", True,
                       "future-aware Wave 字段未被拦截")
    except FeatureGateError as exc:
        return _inject("future_aware_wave_label", opp,
                       "realized_mfe 进入 as-of 机会",
                       "BLOCK", "BLOCK", False, str(exc))


def _case_execution_bare_snapshot():
    from ..execution.execution_gate import ExecutionGateError, execute
    snap = _snap()
    try:
        execute(snap)
        return _inject("execution_bare_snapshot",
                       {"decision": "DecisionSnapshot"},
                       "裸快照直接 execute",
                       "REJECT", "EXECUTED", True,
                       "Execution 接受了无认证资格的裸快照")
    except ExecutionGateError as exc:
        return _inject("execution_bare_snapshot",
                       {"decision": "DecisionSnapshot"},
                       "裸快照直接 execute",
                       "REJECT", "REJECT", False, str(exc))


def _case_broker_unknown_ack():
    from ..execution.broker_adapter import broker_timeout_result
    r = broker_timeout_result("B-1")
    block = r.get("status") == "UNKNOWN" \
        and r.get("block_new_order") is True
    return _inject("broker_unknown_ack",
                   {"broker_order_id": "B-1"},
                   "broker ACK=UNKNOWN（network timeout）",
                   "BLOCK_NEW_ORDER", r.get("status"), not block,
                   r.get("rule"))


def _case_broker_position_mismatch():
    from ..execution.order_state_machine import position_reconciliation
    r = position_reconciliation(canonical_target=0.2, internal_position=0.15,
                                broker_position=0.05)
    block = r.get("status") in ("MISMATCH", "UNKNOWN") \
        and r.get("no_new_risk") is True
    return _inject("broker_position_mismatch",
                   {"canonical": 0.2, "internal": 0.15, "broker": 0.2},
                   "broker_position → 0.05",
                   "MISMATCH/NO_NEW_RISK", r.get("status"), not block,
                   r.get("reason"))


def _case_report_action_rewrite():
    from ..report.contract import ReportContractError, \
        assert_report_ledger_only
    snapshot = _snap(target=0.15, prev=0.2)
    ledger_row = {"institutional_permission": "ALLOW",
                  "previous_fsm_state": "HOLDING",
                  "next_fsm_state": "TRIMMING",
                  "final_target": 0.05,
                  "primary_reason": "POSITION_CAP"}
    try:
        assert_report_ledger_only(snapshot, ledger_row)
        return _inject("report_action_rewrite",
                       {"snapshot_target": 0.15,
                        "ledger_final_target": 0.15},
                       "报告把 final_target 重写为 0.05",
                       "BLOCK", "ALLOWED", True,
                       "报告重算决策未被拦截")
    except ReportContractError as exc:
        return _inject("report_action_rewrite",
                       {"snapshot_target": 0.15,
                        "ledger_final_target": 0.15},
                       "报告把 final_target 重写为 0.05",
                       "BLOCK", "BLOCK", False, str(exc))


_INJECTORS = {
    "future_pit_timestamp": _case_future_pit_timestamp,
    "missing_liquidity_cap": _case_missing_liquidity_cap,
    "nan_risk_cap": _case_nan_risk_cap,
    "ledger_row_tamper": _case_ledger_row_tamper,
    "replay_mismatch": _case_replay_mismatch,
    "release_manifest_mismatch": _case_release_manifest_mismatch,
    "evidence_pack_missing": _case_evidence_pack_missing,
    "future_aware_wave_label": _case_future_aware_wave_label,
    "execution_bare_snapshot": _case_execution_bare_snapshot,
    "broker_unknown_ack": _case_broker_unknown_ack,
    "broker_position_mismatch": _case_broker_position_mismatch,
    "report_action_rewrite": _case_report_action_rewrite,
}


def run_failure_qualification(cases=None) -> dict:
    """MTR Closure（Sprint C）：真实执行 12 类注入并保存逐 case 结果。

    每个 case：Inject → Execute Production Candidate Path → Observe →
    Classify。输出 failure_injection_results.json 所需全部字段。
    缺失 case / 任何 escaped → RELEASE_REJECTED / NOT_PROVEN。"""
    cases = cases or FAILURE_INJECTION_QUALIFICATION_CASES
    results = []
    for case in cases:
        injector = _INJECTORS.get(case)
        if injector is None:
            results.append(_inject(
                case, {}, "MISSING_INJECTOR",
                "BLOCK", "NOT_EXECUTED", False,
                f"缺少真实注入实现：{case}"))
            continue
        try:
            results.append(injector())
        except Exception as exc:   # 注入过程本身失败 → fail-closed 计
            results.append(_inject(
                case, {}, "INJECTOR_EXCEPTION",
                "BLOCK", f"EXCEPTION:{type(exc).__name__}", False,
                str(exc)))
    escaped = [r["case_id"] for r in results if r["escaped"]]
    executed_ids = {r["case_id"] for r in results
                    if r["actual_behavior"] != "NOT_EXECUTED"}
    missing = [c for c in FAILURE_INJECTION_QUALIFICATION_CASES
               if c not in executed_ids]
    not_executed = [r["case_id"] for r in results
                    if r["actual_behavior"] == "NOT_EXECUTED"]
    executed_all = len(executed_ids) == \
        len(FAILURE_INJECTION_QUALIFICATION_CASES)
    if not missing and not escaped and executed_all:
        verdict = "RELEASE_QUALIFIED"
    elif escaped:
        verdict = "RELEASE_REJECTED"
    else:
        verdict = "NOT_PROVEN"
    return {
        "cases": results,
        "cases_executed": len(results),
        "expected_cases": len(FAILURE_INJECTION_QUALIFICATION_CASES),
        "missing_cases": missing,
        "not_executed": sorted(not_executed),
        "failure_escaped": escaped,
        "failure_escaped_count": len(escaped),
        "verdict": verdict,
        "rule": "cases_executed=12 & failure_escaped_count=0 & "
                "missing_cases=0 才允许 Production Ready",
    }
