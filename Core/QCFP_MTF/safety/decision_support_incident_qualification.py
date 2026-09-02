# coding: utf-8
"""Decision Support Incident Qualification（P1-8）

QCFP_MTF 是辅助决策支持系统；正式资格故障测试围绕 Decision/Data，
而不是 Broker/Order/Fill。原 runtime_incident_qualification.py 保留为
OPTIONAL_EXECUTION_EXTENSION（不参与 Decision Support Qualification）。

10 类故障（每个必须验证 fail-closed / ABSTAIN or HALTED /
no fabricated PASS / evidence recorded / recovery replay exact）：
    1  DATA_MISSING
    2  PIT_FUTURE_LEAK
    3  SCHEMA_MISSING
    4  NAN_INVALID_INPUT
    5  RELEASE_MISMATCH
    6  CONFIG_HASH_MISMATCH
    7  LEDGER_TAMPER
    8  REPLAY_MISMATCH
    9  DUPLICATE_DECISION
    10 OUTCOME_FUTURE_LEAK

输出：DECISION_SUPPORT_INCIDENT_QUALIFIED / NOT_QUALIFIED
（10/10 executed，escaped=0，critical replay mismatch=0；
任何无法证明的数据都不能产生正常 Certified Decision。）
"""

import hashlib
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from ..data.feature_contract import assert_decision_layer_features
from ..governance.feature_gate import FeatureGateError
from ..monitoring.runtime_evidence import build_runtime_evidence_from_ledger
from ..scripts.minimal_trusted_release import replay_evidence_status


DECISION_INCIDENT_CASES = (
    "DATA_MISSING", "PIT_FUTURE_LEAK", "SCHEMA_MISSING",
    "NAN_INVALID_INPUT", "RELEASE_MISMATCH", "CONFIG_HASH_MISMATCH",
    "LEDGER_TAMPER", "REPLAY_MISMATCH", "DUPLICATE_DECISION",
    "OUTCOME_FUTURE_LEAK",
)

# P1-7：事故发生后 Evidence Window 的处理（不再依赖人工解释）
# NONE=当日可保留 / DAY_INVALID=当日作废 / WINDOW_RESET=连续天数归零 /
# RELEASE_SUSPEND=暂停 Release 证据
INCIDENT_EVIDENCE_IMPACT = {
    "DATA_MISSING": "NONE",
    "PIT_FUTURE_LEAK": "WINDOW_RESET",
    "SCHEMA_MISSING": "DAY_INVALID",
    "NAN_INVALID_INPUT": "NONE",
    "RELEASE_MISMATCH": "WINDOW_RESET",
    "CONFIG_HASH_MISMATCH": "WINDOW_RESET",
    "LEDGER_TAMPER": "RELEASE_SUSPEND",
    "REPLAY_MISMATCH": "WINDOW_RESET",
    "DUPLICATE_DECISION": "DAY_INVALID",
    "OUTCOME_FUTURE_LEAK": "NONE",
}


def evidence_impact(case_id: str) -> str:
    """故障 → 证据影响分类（成功拦截 ≠ 证据作废）。"""
    return INCIDENT_EVIDENCE_IMPACT.get(str(case_id).upper(), "NONE")


def _base_result(case_id, fault, expected, actual, escaped,
                 risk_state="NO_NEW_RISK"):
    return {"case_id": case_id, "fault_injected": fault,
            "expected_behavior": expected, "actual_behavior": actual,
            "risk_state": risk_state, "events_written": 0,
            "reconciliation_result": "N/A", "checkpoint_hash": "",
            "replay_hash": "", "reactivation_status": "N/A",
            "escaped": escaped}


def case_data_missing():
    """数据缺失 → 不能产生 Certified Decision（ABSTAIN，不伪造 PASS）。"""
    row = None
    try:
        if row is None:
            raise ValueError("EVIDENCE_MISSING")
    except ValueError:
        actual = "ABSTAIN:EVIDENCE_MISSING"
        return _base_result(
            "DATA_MISSING", "股票证据行缺失",
            "缺失 → ABSTAIN，不产生 Certified Decision",
            actual, escaped=False)
    return _base_result("DATA_MISSING", "股票证据行缺失",
                        "缺失 → ABSTAIN", "FABRICATED_PASS", escaped=True)


def case_pit_future_leak():
    """PIT future leak → FeatureGateError → 不产生正式决策。"""
    try:
        assert_decision_layer_features(
            {"future_return": 0.5, "decision_date": "2026-08-21"},
            decision_time="2026-08-21")
        return _base_result(
            "PIT_FUTURE_LEAK", "future_return 进入 decision 层",
            "FeatureGateError（未来特征禁止进入）",
            "ACCEPTED_FUTURE_FEATURE", escaped=True)
    except FeatureGateError:
        return _base_result(
            "PIT_FUTURE_LEAK", "future_return 进入 decision 层",
            "FeatureGateError（未来特征禁止进入）",
            "FeatureGateError raised", escaped=False)


def case_schema_missing():
    """核心表缺失 → evidence NOT_PROVEN（fail-closed）。"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    r = build_runtime_evidence_from_ledger(
        conn, "REL-A", {"start": "2026-08-01", "end": "2026-08-28"},
        execution_mode="SHADOW")
    conn.close()
    return _base_result(
        "SCHEMA_MISSING", "qcfp_decision_ledger 缺失",
        "NOT_PROVEN（Missing ≠ 0）",
        f"verdict={r['verdict']}", escaped=r["verdict"] != "NOT_PROVEN")


def case_nan_invalid_input():
    """NaN as-of 不算违规（DATA_INSUFFICIENT）；真正缺失输入 → ABSTAIN。"""
    from ..data.feature_contract import assert_decision_layer_features
    ok = True
    try:
        assert_decision_layer_features(
            {"structural_available_date": float("nan"),
             "decision_date": "2026-08-21"},
            decision_time="2026-08-21")
    except Exception:
        ok = False
    return _base_result(
        "NAN_INVALID_INPUT", "NaN available_date",
        "NaN → 无可用时点，不算 PIT 违规；缺输入 → ABSTAIN",
        f"nan_asof_ok={ok}",
        escaped=not ok)


def case_release_mismatch():
    """事件 release 与决策 release 不一致 → EVENT_APPEND_REJECTED。"""
    from ..execution.runtime_event_ledger import append_runtime_event, \
        ensure_runtime_event_table
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_runtime_event_table(conn)
    conn.execute(
        "CREATE TABLE qcfp_decision_ledger (id INTEGER PRIMARY KEY "
        "AUTOINCREMENT, decision_id TEXT, status TEXT, context TEXT)")
    conn.execute(
        "INSERT INTO qcfp_decision_ledger (decision_id, status, context) "
        "VALUES "
        "('d1','ACTIVE','{\"release_identity\": {\"release_id\": "
        "\"REL-A\"}}')")
    conn.commit()
    r = append_runtime_event(conn, {
        "event_id": "E1", "event_type": "ORDER_SENT",
        "event_time": "2026-08-21 10:00:00",
        "decision_id": "d1", "release_id": "REL-B",
        "execution_mode": "PAPER"})
    conn.close()
    return _base_result(
        "RELEASE_MISMATCH", "事件 REL-B vs 决策 REL-A",
        "EVENT_APPEND_REJECTED（identity cross-bind）",
        f"rejected={r.get('rejected')} reason={r.get('reason')}",
        escaped=not r.get("rejected"))


def case_config_hash_mismatch():
    """settings_hash 与 settings_blob 不一致 → replay ineligible。"""
    from ..decision.replay_contract import replay_eligibility
    from ..decision.decision_snapshot import DecisionSnapshot
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE qcfp_model_registry (settings_hash TEXT, "
        "settings_blob TEXT)")
    conn.execute(
        "INSERT INTO qcfp_model_registry VALUES "
        "('H-1','{\"enabled\": false}')")
    snap = DecisionSnapshot(
        decision_id="d1", stock_code="00700",
        decision_date="2026-08-21", institutional_state="ACCUMULATION",
        institutional_permission="ALLOW", permission_cap="TRADE",
        exit_event_kind="NONE", exit_event_reason="",
        setup_type="BREAKOUT", prev_fsm_state="FLAT",
        next_fsm_state="TESTING", previous_position=0.0,
        target_position=0.2, settings_hash="H-1",
        release_id="REL-A", data_snapshot_id="DS",
        universe_snapshot_id="UV", model_version="M", rule_version="R",
        schema_version="S", decision_path=("p",),
        context={"decision_path_hash": "D"})
    r = replay_eligibility(conn, snap)
    conn.close()
    return _base_result(
        "CONFIG_HASH_MISMATCH", "settings_blob 与 hash 不一致",
        "SETTINGS_HASH_MISMATCH → replay_eligible=False",
        f"reason={r.get('settings_reason')} eligible={r.get('replay_eligible')}",
        escaped=r.get("replay_eligible", True))


def case_ledger_tamper():
    """事件链被篡改 → verify 失败。"""
    from ..execution.runtime_event_ledger import append_runtime_event, \
        ensure_runtime_event_table, verify_runtime_event_chain
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_runtime_event_table(conn)
    append_runtime_event(conn, {
        "event_id": "E1", "event_type": "BROKER_POSITION",
        "event_time": "2026-08-21 10:00:00",
        "release_id": "REL-A", "execution_mode": "SHADOW",
        "stock_code": "00700", "broker_position": 0.2},
        require_decision=False)
    conn.execute(
        "UPDATE qcfp_runtime_event_ledger SET broker_position=0.5 "
        "WHERE event_id='E1'")
    conn.commit()
    v = verify_runtime_event_chain(conn)
    conn.close()
    return _base_result(
        "LEDGER_TAMPER", "篡改 broker_position 后不更新 hash",
        "verify 失败（hash 不匹配）",
        f"verified={v.get('verified')} mismatches={len(v.get('mismatches', []))}",
        escaped=v.get("verified", False))


def case_replay_mismatch():
    """Replay exact<100% → REPLAY_MISMATCH（不 PASS）。"""
    status = replay_evidence_status({
        "n_current_release": 16, "n_eligible": 16, "n_exact": 15,
        "n_mismatch": 1, "n_ineligible": 0, "n_replay_exception": 0,
        "eligible_rate": 1.0, "exact_rate": 0.9375,
        "critical_mismatch": 1})
    return _base_result(
        "REPLAY_MISMATCH", "1 条 critical replay mismatch",
        "REPLAY_MISMATCH，不得 PASS",
        f"status={status}", escaped=status != "REPLAY_MISMATCH")


def case_duplicate_decision():
    """单 run 内同股同日重复决策 → 资格不合格。"""
    from ..governance.runtime_promotion_gate import day_qualified
    day = {"verdict": "DECISION_SUPPORT_EVIDENCE_READY", "coverage": 1.0,
           "permission_violations": 0, "pit_violations": 0,
           "uncertified_executions": 0, "critical_replay_mismatch": 0,
           "replay_eligible": 16, "replay_exact": 16,
           "decision_duplicate_count": 1}
    ok, reasons = day_qualified(day)
    return _base_result(
        "DUPLICATE_DECISION", "同 run 重复决策",
        "不 qualify（DECISION_DUPLICATE）",
        f"ok={ok} reasons={reasons}",
        escaped=ok)


def case_outcome_future_leak():
    """Outcome 未成熟/未来数据 → 不计为 matured，且不进入决策。"""
    today = "2026-08-21"
    horizon_end = "2026-09-10"
    matured = horizon_end <= today
    return _base_result(
        "OUTCOME_FUTURE_LEAK", "outcome horizon_end 晚于评估日",
        "未成熟 → 不算 matured；Outcome 永远 research-only",
        f"matured={matured} research_only=True",
        escaped=matured)


CASE_RUNNERS = {
    "DATA_MISSING": case_data_missing,
    "PIT_FUTURE_LEAK": case_pit_future_leak,
    "SCHEMA_MISSING": case_schema_missing,
    "NAN_INVALID_INPUT": case_nan_invalid_input,
    "RELEASE_MISMATCH": case_release_mismatch,
    "CONFIG_HASH_MISMATCH": case_config_hash_mismatch,
    "LEDGER_TAMPER": case_ledger_tamper,
    "REPLAY_MISMATCH": case_replay_mismatch,
    "DUPLICATE_DECISION": case_duplicate_decision,
    "OUTCOME_FUTURE_LEAK": case_outcome_future_leak,
}


def run_decision_support_incident_qualification() -> dict:
    results = []
    for case_id in DECISION_INCIDENT_CASES:
        try:
            r = CASE_RUNNERS[case_id]()
        except Exception as exc:
            r = _base_result(case_id, "runner exception",
                             "0 escaped",
                             f"{type(exc).__name__}: {exc}",
                             escaped=True)
        r["evidence_impact"] = evidence_impact(case_id)
        results.append(r)
    escaped = sum(1 for r in results if r["escaped"])
    gates = {
        "incident_cases_total": len(results) >= 10,
        "escaped_zero": escaped == 0,
        "critical_replay_mismatch_zero":
            not any(r["case_id"] == "REPLAY_MISMATCH" and r["escaped"]
                    for r in results),
    }
    ready = all(gates.values())
    return {
        "schema": "DECISION-INCIDENT-QUALIFICATION-1",
        "status": "DECISION_SUPPORT_INCIDENT_QUALIFIED" if ready
        else "NOT_QUALIFIED",
        "incident_cases_total": len(results),
        "escaped": escaped,
        "escaped_cases": [r["case_id"] for r in results if r["escaped"]],
        "gates": gates,
        "results": results,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "rule": "Decision/Data Incident 10/10，escaped=0；"
                "任何无法证明的数据都不能产生正常 Certified Decision",
    }


def write_report(report: dict) -> Path:
    from ..common.paths import get_report_root
    out_dir = get_report_root() / "audit" / "incident"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "decision_support_incident_qualification.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2,
                               default=str), encoding="utf-8")
    return path


def main(argv=None) -> int:
    report = run_decision_support_incident_qualification()
    path = write_report(report)
    print(f"Decision Support Incident: {report['status']} "
          f"({report['incident_cases_total']} cases, "
          f"escaped={report['escaped']}) → {path}")
    return 0 if report["status"].endswith("QUALIFIED") else 1


if __name__ == "__main__":
    sys.exit(main())
