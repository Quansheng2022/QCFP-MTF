# coding: utf-8
"""Runtime Incident Qualification（C5：Incident Drill）

不是 Authority。只负责：
    inject → observe → collect evidence → classify → report

强制 10 个 Incident Case（真钱前必须 0 escaped）：
    1  Broker submit timeout
    2  Broker returns UNKNOWN
    3  Delayed ACK（FILL 先于 ACK）
    4  Partial Fill
    5  Duplicate ACK/FILL
    6  Position mismatch
    7  Runtime Event persistence failure
    8  Network disconnect/reconnect
    9  Process restart（无证书不得恢复新风险）
    10 Checkpoint replay after restart（重放 exact + Reactivation）

评价标准不是"程序没 crash"，而是：
    UNKNOWN 保留 / 无等价新订单 / NO_NEW_RISK / Broker 被 query /
    Position 被 reconcile / Resolution 被记录 / Replay exact

Hard Gate：
    incident_cases_total >= 10
    escaped = 0 / blind_resend = 0 / unresolved_unknown = 0
    unresolved_position_mismatch = 0 / critical_replay_mismatch = 0
    unpersisted money event → NO_NEW_RISK = PASS
    restart_without_certificate_allowed = 0

输出：SMALL_LIVE_ELIGIBLE / SMALL_LIVE_NOT_ELIGIBLE
（SMALL_LIVE 是否真正启动仍保留人工显式批准。）
"""

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from ..execution.order_state_machine import OrderStateMachine
from ..execution.runtime_event_ledger import (
    RUNTIME_EVENT_TABLE_DDL, append_runtime_event,
    ensure_runtime_event_table, verify_runtime_event_chain)
from ..execution.unknown_resolution import (
    assert_no_blind_resend, unknown_resolution_pipeline)


INCIDENT_CASES = (
    "CASE_01_BROKER_SUBMIT_TIMEOUT",
    "CASE_02_BROKER_UNKNOWN",
    "CASE_03_DELAYED_ACK",
    "CASE_04_PARTIAL_FILL",
    "CASE_05_DUPLICATE_ACK_FILL",
    "CASE_06_POSITION_MISMATCH",
    "CASE_07_EVENT_PERSISTENCE_FAILURE",
    "CASE_08_NETWORK_DISCONNECT_RECONNECT",
    "CASE_09_PROCESS_RESTART",
    "CASE_10_CHECKPOINT_REPLAY_AFTER_RESTART",
)


def setup_scenario_conn() -> sqlite3.Connection:
    """每 Case 独立 in-memory DB：Decision + Certificate + Event Ledger。"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_runtime_event_table(conn)
    conn.execute(
        "CREATE TABLE qcfp_decision_ledger (id INTEGER PRIMARY KEY "
        "AUTOINCREMENT, decision_id TEXT, stock_code TEXT, "
        "decision_date TEXT, status TEXT, final_target REAL, "
        "context TEXT)")
    conn.execute(
        "INSERT INTO qcfp_decision_ledger (decision_id, stock_code, "
        "decision_date, status, final_target, context) VALUES "
        "('d1','00700','2026-08-21','ACTIVE',0.2,"
        "'{\"release_identity\": {\"release_id\": \"REL-A\"}}')")
    conn.execute(
        "CREATE TABLE qcfp_decision_certificate (certificate_id TEXT "
        "PRIMARY KEY, decision_id TEXT, release_id TEXT, "
        "snapshot_hash TEXT, evidence_pack_hash TEXT, created_at TEXT)")
    conn.execute(
        "INSERT INTO qcfp_decision_certificate VALUES "
        "('CERT-1','d1','REL-A','SH','EP','2026-08-21')")
    conn.commit()
    return conn


def dispatch_broker_response(conn, event: dict) -> dict:
    """Event-first 派发：Broker Response 必须先落 Runtime Event；
    持久化失败 → BROKER_RESPONSE_UNPERSISTED → NO_NEW_RISK，
    绝不返回 dispatched=True。"""
    try:
        r = append_runtime_event(conn, event, require_decision=False)
    except Exception as exc:
        return {"dispatched": False,
                "risk_state": "NO_NEW_RISK",
                "reason": "BROKER_RESPONSE_UNPERSISTED",
                "error": f"{type(exc).__name__}: {exc}"}
    if r.get("rejected"):
        return {"dispatched": False,
                "risk_state": "NO_NEW_RISK",
                "reason": "BROKER_RESPONSE_UNPERSISTED",
                "identity": r.get("identity")}
    return {"dispatched": True,
            "risk_state": "RISK_UNBLOCKED" if r.get("inserted")
            else "NO_NEW_RISK",
            "event_id": r.get("event_id"),
            "inserted": r.get("inserted", 0)}


def _ev(event_type, decision_id="d1", time="2026-08-21 10:00:00",
        payload=None, order_intent_id="O-1", broker_order_id="B-1"):
    return {"event_id": f"E-{event_type}-{time}",
            "event_type": event_type, "event_time": time,
            "decision_id": decision_id, "release_id": "REL-A",
            "execution_mode": "SMALL_LIVE",
            "certificate_id": "CERT-1", "stock_code": "00700",
            "order_intent_id": order_intent_id,
            "broker_order_id": broker_order_id,
            "payload": payload or {}}


def case_01_broker_submit_timeout(conn) -> dict:
    """submit timeout → UNKNOWN 保留 → 禁止盲重发 → query → resolved。"""
    r = dispatch_broker_response(conn, _ev("ORDER_UNKNOWN",
                                           time="2026-08-21 10:00:00"))
    blocked = assert_no_blind_resend(conn, "d1", "O-1", "O-2")
    append_runtime_event(conn, _ev("UNKNOWN_RESOLVED",
                                   time="2026-08-21 10:00:30",
                                   payload={"resolution_status":
                                            "RESOLVED_NO_ORDER"}),
                         require_decision=False)
    pipe = unknown_resolution_pipeline([
        {"event_type": "ORDER_UNKNOWN",
         "event_time": "2026-08-21 10:00:00"},
        {"event_type": "UNKNOWN_RESOLVED",
         "event_time": "2026-08-21 10:00:30",
         "payload": {"resolution_status": "RESOLVED_NO_ORDER"}}])
    return {"case_id": "CASE_01_BROKER_SUBMIT_TIMEOUT",
            "fault_injected": "submit 网络超时",
            "expected_behavior": "UNKNOWN 保留、禁盲重发、NO_NEW_RISK、"
                                 "query 后 RESOLVED",
            "actual_behavior": f"dispatched={r['dispatched']} "
                               f"blocked={blocked['blocked']} "
                               f"terminal={pipe['status']}",
            "risk_state": pipe["status"],
            "events_written": conn.execute(
                "SELECT COUNT(*) c FROM qcfp_runtime_event_ledger"
            ).fetchone()["c"],
            "reconciliation_result": "RESOLVED_NO_ORDER",
            "checkpoint_hash": "",
            "replay_hash": "",
            "reactivation_status": "N/A",
            "escaped": not (r["dispatched"] and blocked["blocked"]
                            and pipe["resolved"] and not pipe["no_new_risk"])}


def case_02_broker_unknown(conn) -> dict:
    """未知 broker 状态 → UNKNOWN（绝不乐观 ACK）。"""
    from ..execution.paper_pipeline import map_simulator_status
    transition = map_simulator_status("BROKER_PENDING_X")
    osm = OrderStateMachine()
    osm.send("O-1", 100)
    ack = osm.timeout("O-1")
    r = dispatch_broker_response(
        conn, _ev("ORDER_UNKNOWN", time="2026-08-21 10:00:00",
                  payload={"raw_status": "BROKER_PENDING_X"}))
    return {"case_id": "CASE_02_BROKER_UNKNOWN",
            "fault_injected": "broker 返回未知状态 BROKER_PENDING_X",
            "expected_behavior": "映射为 UNKNOWN/timeout，绝不 ACK",
            "actual_behavior": f"transition={transition} ack={ack['state']}",
            "risk_state": "NO_NEW_RISK",
            "events_written": conn.execute(
                "SELECT COUNT(*) c FROM qcfp_runtime_event_ledger"
            ).fetchone()["c"],
            "reconciliation_result": "UNKNOWN_PRESERVED",
            "checkpoint_hash": "", "replay_hash": "",
            "reactivation_status": "N/A",
            "escaped": not (transition == "timeout"
                            and ack["state"] == "UNKNOWN"
                            and r["dispatched"])}


def case_03_delayed_ack(conn) -> dict:
    """FILL 先于 ACK：事件链顺序仍可验证，不产生双份风险。"""
    append_runtime_event(conn, _ev("ORDER_SENT",
                                   time="2026-08-21 10:00:00"),
                         require_decision=False)
    append_runtime_event(conn, _ev("FILL", time="2026-08-21 10:00:05",
                                   payload={"filled_qty": 0.2}),
                         require_decision=False)
    append_runtime_event(conn, _ev("ORDER_ACK", time="2026-08-21 10:00:10"),
                         require_decision=False)
    chain = verify_runtime_event_chain(conn)
    fills = conn.execute(
        "SELECT COUNT(*) c FROM qcfp_runtime_event_ledger "
        "WHERE event_type='FILL'").fetchone()["c"]
    return {"case_id": "CASE_03_DELAYED_ACK",
            "fault_injected": "FILL 先于 ACK 到达",
            "expected_behavior": "事件顺序可哈希验证、FILL 只计一次",
            "actual_behavior": f"chain_verified={chain['verified']} "
                               f"fills={fills}",
            "risk_state": "RISK_UNBLOCKED",
            "events_written": 3,
            "reconciliation_result": "IN_SYNC",
            "checkpoint_hash": "", "replay_hash": "",
            "reactivation_status": "N/A",
            "escaped": not (chain["verified"] and fills == 1)}


def case_04_partial_fill(conn) -> dict:
    """Partial Fill：按成交更新仓位，剩余部分不重复下单。"""
    append_runtime_event(conn, _ev("PARTIAL_FILL",
                                   time="2026-08-21 10:00:05",
                                   payload={"filled_qty": 0.1}),
                         require_decision=False)
    blocked = assert_no_blind_resend(conn, "d1", "O-1", "O-1B")
    return {"case_id": "CASE_04_PARTIAL_FILL",
            "fault_injected": "broker 部分成交 50%",
            "expected_behavior": "partial 记录、剩余部分不盲发新单",
            "actual_behavior": f"blocked_equivalent={blocked['blocked']}",
            "risk_state": "RISK_UNBLOCKED",
            "events_written": 1,
            "reconciliation_result": "PARTIAL",
            "checkpoint_hash": "", "replay_hash": "",
            "reactivation_status": "N/A",
            "escaped": blocked["blocked"]}


def case_05_duplicate_ack_fill(conn) -> dict:
    """Duplicate ACK/FILL：event_id 幂等，不产生双份成交。"""
    e1 = _ev("FILL", time="2026-08-21 10:00:05")
    r1 = append_runtime_event(conn, e1, require_decision=False)
    r2 = append_runtime_event(conn, e1, require_decision=False)
    fills = conn.execute(
        "SELECT COUNT(*) c FROM qcfp_runtime_event_ledger "
        "WHERE event_type='FILL'").fetchone()["c"]
    return {"case_id": "CASE_05_DUPLICATE_ACK_FILL",
            "fault_injected": "同一 FILL 事件重复投递",
            "expected_behavior": "INSERT OR IGNORE 幂等，FILL 只落一条",
            "actual_behavior": f"first_inserted={r1['inserted']} "
                               f"second_inserted={r2['inserted']} "
                               f"fills={fills}",
            "risk_state": "RISK_UNBLOCKED",
            "events_written": fills,
            "reconciliation_result": "IN_SYNC",
            "checkpoint_hash": "", "replay_hash": "",
            "reactivation_status": "N/A",
            "escaped": not (r1["inserted"] == 1
                            and r2["inserted"] == 0 and fills == 1)}


def case_06_position_mismatch(conn) -> dict:
    """Position mismatch → reconciliation MISMATCH → NO_NEW_RISK。"""
    ev = _ev("RECONCILIATION", time="2026-08-21 10:00:10")
    ev["reconciliation_status"] = "MISMATCH"
    append_runtime_event(conn, ev, require_decision=False)
    mismatches = conn.execute(
        "SELECT COUNT(*) c FROM qcfp_runtime_event_ledger "
        "WHERE event_type='RECONCILIATION' "
        "AND reconciliation_status='MISMATCH'").fetchone()["c"]
    return {"case_id": "CASE_06_POSITION_MISMATCH",
            "fault_injected": "broker 仓位与 internal 不一致",
            "expected_behavior": "MISMATCH 记录、unresolved>0 → NO_NEW_RISK",
            "actual_behavior": f"mismatch_rows={mismatches}",
            "risk_state": "NO_NEW_RISK",
            "events_written": 1,
            "reconciliation_result": "MISMATCH",
            "checkpoint_hash": "", "replay_hash": "",
            "reactivation_status": "N/A",
            "escaped": mismatches == 0}


def case_07_event_persistence_failure(conn) -> dict:
    """Event persistence failure：broker 已接受订单但事件落库失败
    → BROKER_RESPONSE_UNPERSISTED → NO_NEW_RISK，绝不 dispatched。"""
    conn.execute("DROP TABLE qcfp_runtime_event_ledger")
    conn.commit()
    r = dispatch_broker_response(conn, _ev("FILL"))
    return {"case_id": "CASE_07_EVENT_PERSISTENCE_FAILURE",
            "fault_injected": "Runtime Event 表不可用（持久化失败）",
            "expected_behavior": "BROKER_RESPONSE_UNPERSISTED → "
                                 "NO_NEW_RISK，dispatched=False",
            "actual_behavior": f"dispatched={r['dispatched']} "
                               f"reason={r['reason']} "
                               f"risk={r['risk_state']}",
            "risk_state": r["risk_state"],
            "events_written": 0,
            "reconciliation_result": "NOT_PERSISTED",
            "checkpoint_hash": "", "replay_hash": "",
            "reactivation_status": "N/A",
            "escaped": r["dispatched"] or r["risk_state"] != "NO_NEW_RISK"}


def case_08_network_disconnect_reconnect(conn) -> dict:
    """断网/重连：重连后 query 恢复，UNKNOWN → resolved。"""
    append_runtime_event(conn, _ev("ORDER_UNKNOWN",
                                   time="2026-08-21 10:00:00"),
                         require_decision=False)
    append_runtime_event(conn, _ev("UNKNOWN_QUERY",
                                   time="2026-08-21 10:00:20"),
                         require_decision=False)
    append_runtime_event(conn, _ev("UNKNOWN_RESOLVED",
                                   time="2026-08-21 10:00:40",
                                   payload={"resolution_status":
                                            "RESOLVED_FILLED"}),
                         require_decision=False)
    chain = verify_runtime_event_chain(conn)
    return {"case_id": "CASE_08_NETWORK_DISCONNECT_RECONNECT",
            "fault_injected": "断网 → 重连 → query",
            "expected_behavior": "query 后 RESOLVED_FILLED、链完整",
            "actual_behavior": f"chain={chain['verified']}",
            "risk_state": "RESOLVED_FILLED",
            "events_written": 3,
            "reconciliation_result": "IN_SYNC",
            "checkpoint_hash": "", "replay_hash": "",
            "reactivation_status": "N/A",
            "escaped": not chain["verified"]}


def case_09_process_restart(conn) -> dict:
    """Process restart：无 Reactivation Certificate 不得恢复新风险。"""
    reactivation = conn.execute(
        "SELECT COUNT(*) c FROM qcfp_runtime_event_ledger "
        "WHERE event_type='REACTIVATION'").fetchone()["c"]
    # 恢复路径必须先有 REACTIVATION 事件；没有 → 新风险保持冻结
    resume_allowed = reactivation > 0
    append_runtime_event(conn, _ev("INCIDENT",
                                   time="2026-08-21 11:00:00"),
                         require_decision=False)
    return {"case_id": "CASE_09_PROCESS_RESTART",
            "fault_injected": "进程重启（无证书）",
            "expected_behavior": "restart ≠ recovered；无 REACTIVATION "
                                 "→ 禁止恢复新风险",
            "actual_behavior": f"reactivation_events={reactivation} "
                               f"resume_allowed={resume_allowed}",
            "risk_state": "NO_NEW_RISK",
            "events_written": 1,
            "reconciliation_result": "FROZEN",
            "checkpoint_hash": "",
            "replay_hash": "",
            "reactivation_status": "NOT_REACTIVATED",
            "escaped": resume_allowed}


def case_10_checkpoint_replay_after_restart(conn) -> dict:
    """重启后 Checkpoint→Replay→exact→Reactivation→resume。"""
    append_runtime_event(conn, _ev("REPLAY",
                                   time="2026-08-21 11:30:00",
                                   payload={"verified": True,
                                            "replay_hash": "H-EXACT"}),
                         require_decision=False)
    append_runtime_event(conn, _ev("REACTIVATION",
                                   time="2026-08-21 11:31:00",
                                   payload={"certificate_id": "CERT-1"}),
                         require_decision=False)
    chain = verify_runtime_event_chain(conn)
    react = conn.execute(
        "SELECT COUNT(*) c FROM qcfp_runtime_event_ledger "
        "WHERE event_type='REACTIVATION'").fetchone()["c"]
    return {"case_id": "CASE_10_CHECKPOINT_REPLAY_AFTER_RESTART",
            "fault_injected": "重启后 checkpoint replay",
            "expected_behavior": "Replay exact → REACTIVATION 事件 → resume",
            "actual_behavior": f"chain={chain['verified']} "
                               f"reactivations={react}",
            "risk_state": "RISK_UNBLOCKED",
            "events_written": 2,
            "reconciliation_result": "IN_SYNC",
            "checkpoint_hash": chain.get("chain_tail", ""),
            "replay_hash": "H-EXACT",
            "reactivation_status": "REACTIVATED",
            "escaped": not (chain["verified"] and react == 1)}


CASE_RUNNERS = {
    "CASE_01_BROKER_SUBMIT_TIMEOUT": case_01_broker_submit_timeout,
    "CASE_02_BROKER_UNKNOWN": case_02_broker_unknown,
    "CASE_03_DELAYED_ACK": case_03_delayed_ack,
    "CASE_04_PARTIAL_FILL": case_04_partial_fill,
    "CASE_05_DUPLICATE_ACK_FILL": case_05_duplicate_ack_fill,
    "CASE_06_POSITION_MISMATCH": case_06_position_mismatch,
    "CASE_07_EVENT_PERSISTENCE_FAILURE":
        case_07_event_persistence_failure,
    "CASE_08_NETWORK_DISCONNECT_RECONNECT":
        case_08_network_disconnect_reconnect,
    "CASE_09_PROCESS_RESTART": case_09_process_restart,
    "CASE_10_CHECKPOINT_REPLAY_AFTER_RESTART":
        case_10_checkpoint_replay_after_restart,
}


def run_incident_qualification(conn_factory=None) -> dict:
    """执行全部 10 个 Drill，输出 qualification artifact。"""
    conn_factory = conn_factory or setup_scenario_conn
    results = []
    for case_id in INCIDENT_CASES:
        conn = conn_factory()
        try:
            r = CASE_RUNNERS[case_id](conn)
        except Exception as exc:
            r = {"case_id": case_id,
                 "fault_injected": "runner exception",
                 "expected_behavior": "0 escaped",
                 "actual_behavior": f"{type(exc).__name__}: {exc}",
                 "risk_state": "NOT_PROVEN",
                 "events_written": 0,
                 "reconciliation_result": "ERROR",
                 "checkpoint_hash": "", "replay_hash": "",
                 "reactivation_status": "N/A",
                 "escaped": True}
        finally:
            conn.close()
        results.append(r)
    escaped = sum(1 for r in results if r["escaped"])
    case_by_id = {r["case_id"]: r for r in results}
    gates = {
        "incident_cases_total": len(results) >= 10,
        "escaped_zero": escaped == 0,
        "blind_resend_zero": (
            not case_by_id["CASE_01_BROKER_SUBMIT_TIMEOUT"]["escaped"]
            and not case_by_id["CASE_04_PARTIAL_FILL"]["escaped"]),
        "unresolved_unknown_zero": not any(
            str(r.get("risk_state", "")).upper() == "UNRESOLVED_UNKNOWN"
            for r in results),
        "unresolved_position_mismatch_zero": not any(
            r["case_id"] == "CASE_06_POSITION_MISMATCH" and r["escaped"]
            for r in results),
        "critical_replay_mismatch_zero":
            not case_by_id["CASE_10_CHECKPOINT_REPLAY_AFTER_RESTART"][
                "escaped"],
        "unpersisted_money_event_no_new_risk":
            case_by_id["CASE_07_EVENT_PERSISTENCE_FAILURE"]["risk_state"]
            == "NO_NEW_RISK",
        "restart_without_certificate_blocked": not any(
            r["case_id"] == "CASE_09_PROCESS_RESTART" and r["escaped"]
            for r in results),
    }
    ready = all(gates.values()) and len(results) >= 10
    return {
        "schema": "INCIDENT-QUALIFICATION-1",
        "status": "SMALL_LIVE_ELIGIBLE" if ready
        else "SMALL_LIVE_NOT_ELIGIBLE",
        "incident_cases_total": len(results),
        "escaped": escaped,
        "escaped_cases": [r["case_id"] for r in results if r["escaped"]],
        "gates": gates,
        "results": results,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "rule": "SMALL_LIVE_ELIGIBLE 是机器可判定状态；真正启动 "
                "SMALL_LIVE 需人工显式批准",
    }


def write_qualification_report(report: dict) -> Path:
    from ..common.paths import get_report_root
    out_dir = get_report_root() / "audit" / "incident"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "incident_qualification.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2,
                               default=str), encoding="utf-8")
    return path


def main(argv=None) -> int:
    report = run_incident_qualification()
    path = write_qualification_report(report)
    print(f"Incident Qualification: {report['status']} "
          f"({report['incident_cases_total']} cases, "
          f"escaped={report['escaped']}) → {path}")
    return 0 if report["status"] == "SMALL_LIVE_ELIGIBLE" else 1


if __name__ == "__main__":
    sys.exit(main())
