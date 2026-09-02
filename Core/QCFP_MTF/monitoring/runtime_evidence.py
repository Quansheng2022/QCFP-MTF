# coding: utf-8
"""Runtime Evidence Artifact（决策支持目标重新对齐：P0-2）

QCFP_MTF 是辅助决策支持系统。正式核心证据 = 六类：
    decision / replay / outcome / stability / risk / data_quality
execution / reconciliation 保留为 OPTIONAL_SIMULATION_EVIDENCE，
不参与 Decision Support Qualification。

Release 在现实世界到底表现怎样的证据（不是决策 Authority）：
    release_identity / period / decision / replay / outcome / stability /
    risk / data_quality / execution(optional) / reconciliation(optional) /
    hard_gates / evidence_hash

Runtime Evidence Wiring 修改：
    * Required Field Contract：每个 section 的必填 key 缺失 →
      UNKNOWN → NOT_PROVEN（消灭 missing → 0 → PASS 的 Fail-Open）；
    * 正式证据只能由 build_runtime_evidence_from_ledger() 从
      Decision Ledger / Runtime Event Ledger / Research Outcome /
      Replay / Incident-Reactivation 构造；
      禁止调用方用裸 dict“告诉系统自己没问题”；
    * 按 Stage 定义 Required Evidence（SHADOW / PAPER / SMALL_LIVE）；
    * Evidence Hash 绑定事实链（decision_ledger_chain_tail +
      runtime_event_chain_tail + outcome_set_hash + replay_hash）；
    * continuous_certification() 只接受 verified artifact（dict），
      裸字符串 → NOT_PROVEN。

Hard Gate 优先于总分：
    PermissionViolation>0 / UncertifiedExecution>0 / PITViolation>0 /
    CriticalReplayMismatch>0 → CERTIFICATION_SUSPENDED
    UnresolvedBrokerUNKNOWN>0 / UnresolvedPositionMismatch>0 → NO_NEW_RISK
"""

import hashlib
import json


EXECUTION_MODES = ("SHADOW", "PAPER", "SMALL_LIVE")

READY_VERDICTS = ("EVIDENCE_READY", "DECISION_SUPPORT_EVIDENCE_READY")

# Required Field Contract：缺失任一 key → NOT_PROVEN（不是 0）
REQUIRED_EVIDENCE_FIELDS = {
    "decision": ("expected_decisions", "actual_decisions", "coverage",
                 "permission_violations", "uncertified_executions",
                 "pit_violations", "safe_mode_count", "halted_count"),
    "replay": ("replay_total", "replay_eligible", "replay_exact",
               "critical_replay_mismatch", "replay_status"),
    "outcome": ("outcome_count", "outcome_coverage",
                "outcome_maturity_5d", "outcome_maturity_20d",
                "outcome_maturity_60d"),
    "stability": ("decision_flip_rate", "duplicate_decisions"),
    "risk": (),
    "data_quality": ("pit_grade_distribution",),
    "execution": ("order_intents", "orders_sent", "fills", "partial_fills",
                  "rejects", "unknown_count", "resolved_unknown",
                  "unresolved_unknown", "blind_resend_count"),
    "reconciliation": ("expected_reconciliations",
                       "actual_reconciliations", "coverage",
                       "mismatch", "unknown", "unresolved_mismatch"),
    "safety": ("incident_count", "recovery_count", "replay_count",
               "critical_replay_mismatch", "reactivation_count"),
}

# 按 Stage 定义 Required Evidence
STAGE_REQUIRED_SECTIONS = {
    "SHADOW": ("decision", "replay", "outcome", "stability", "risk",
               "data_quality"),
    "PAPER": ("decision", "replay", "outcome", "stability", "risk",
              "data_quality", "execution", "reconciliation"),
    "SMALL_LIVE": ("decision", "replay", "outcome", "stability", "risk",
                   "data_quality", "execution", "reconciliation"),
}


def _required_missing(section: dict, section_name: str) -> list:
    """section 存在但必填 key 缺失 → 返回缺失列表。"""
    section = section or {}
    return [k for k in REQUIRED_EVIDENCE_FIELDS.get(section_name, ())
            if k not in section or section[k] is None]


def _stage_missing(execution_mode: str, evidence: dict) -> list:
    mode = str(execution_mode or "").upper()
    if mode not in EXECUTION_MODES:
        return ["UNKNOWN_EXECUTION_MODE"]
    missing = []
    for section_name in STAGE_REQUIRED_SECTIONS.get(mode, ()):
        section = evidence.get(section_name)
        if section is None:
            missing.append(f"{section_name}:section_missing")
        else:
            missing.extend(
                f"{section_name}:{k}"
                for k in _required_missing(section, section_name))
    if mode == "SHADOW":
        # 决策支持：execution/reconciliation 是 OPTIONAL_SIMULATION_EVIDENCE，
        # 不参与 Qualification；但 section 存在时必须显式标记 optional。
        for opt in ("execution", "reconciliation"):
            sec = evidence.get(opt)
            if sec is not None and sec.get("applicable") not in (
                    "OPTIONAL_SIMULATION_EVIDENCE", "NOT_APPLICABLE"):
                missing.append(f"{opt}:applicable=OPTIONAL_required")
    return missing


def runtime_evidence_artifact(identity=None, period=None, decision=None,
                              replay=None, outcome=None, stability=None,
                              data_quality=None, risk=None,
                              execution=None, reconciliation=None,
                              safety=None, opportunity=None,
                              hard_gates=None,
                              execution_mode="SHADOW") -> dict:
    """聚合真实证据；None 字段或必填 key 缺失 → NOT_PROVEN。"""
    evidence = {
        "release_identity": identity,
        "period": period,
        "decision": decision,
        "replay": replay,
        "outcome": outcome,
        "stability": stability,
        "data_quality": data_quality,
        "risk": risk,
        "execution": execution,
        "reconciliation": reconciliation,
        "safety": safety,
        "opportunity": opportunity,
    }
    OPTIONAL_SECTIONS = ("execution", "reconciliation", "safety",
                         "opportunity")
    missing = [k for k, v in evidence.items()
               if v is None and k not in OPTIONAL_SECTIONS]
    missing_keys = []
    mode = str(execution_mode or "").upper()
    required_sections = STAGE_REQUIRED_SECTIONS.get(mode, ())
    for section_name in required_sections:
        if evidence.get(section_name) is not None:
            missing_keys.extend(
                f"{section_name}:{k}"
                for k in _required_missing(evidence[section_name],
                                           section_name))
    missing_keys.extend(_stage_missing(execution_mode, evidence))
    if missing or missing_keys:
        return {"verdict": "NOT_PROVEN",
                "missing_sections": missing,
                "missing_required_keys": missing_keys,
                "evidence_hash": "",
                "rule": "Runtime Evidence 必须来自真实 "
                        "Ledger/Event/Outcome；缺 key → NOT_PROVEN，"
                        "绝不 missing → 0 → PASS"}
    raw = json.dumps(evidence, sort_keys=True, ensure_ascii=False,
                     default=str)
    evidence_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    gates = runtime_evidence_hard_gates(evidence, hard_gates)
    verdict = "DECISION_SUPPORT_EVIDENCE_READY" \
        if mode == "SHADOW" and gates["ok"] else \
        ("EVIDENCE_READY" if gates["ok"] else gates["state"])
    return {"evidence": evidence,
            "hard_gates": gates,
            "evidence_hash": evidence_hash,
            "execution_mode": execution_mode,
            "verdict": verdict}


def runtime_evidence_hard_gates(evidence: dict,
                                hard_gates: dict = None) -> dict:
    """硬门优先于总分。"""
    g = hard_gates or {}
    decision = evidence.get("decision") or {}
    execution = evidence.get("execution") or {}
    reconciliation = evidence.get("reconciliation") or {}
    safety = evidence.get("safety") or {}
    suspend = []
    if int(decision.get("permission_violations") or 0) > 0:
        suspend.append("PERMISSION_VIOLATION")
    if int(decision.get("uncertified_executions") or 0) > 0:
        suspend.append("UNCERTIFIED_EXECUTION")
    if int(decision.get("pit_violations") or 0) > 0:
        suspend.append("PIT_VIOLATION")
    if int(safety.get("critical_replay_mismatch") or 0) > 0:
        suspend.append("CRITICAL_REPLAY_MISMATCH")
    no_new_risk = []
    if int(execution.get("unresolved_unknown") or 0) > 0:
        no_new_risk.append("UNRESOLVED_BROKER_UNKNOWN")
    if int(reconciliation.get("unresolved_mismatch") or 0) > 0:
        no_new_risk.append("UNRESOLVED_POSITION_MISMATCH")
    if suspend:
        return {"ok": False, "state": "CERTIFICATION_SUSPENDED",
                "suspend_reasons": suspend,
                "no_new_risk": no_new_risk}
    if no_new_risk:
        return {"ok": False, "state": "NO_NEW_RISK",
                "suspend_reasons": [], "no_new_risk": no_new_risk}
    return {"ok": True, "state": "PASS",
            "suspend_reasons": [], "no_new_risk": []}


def continuous_certification(evidence_artifact) -> str:
    """持续认证：只接受 verified RuntimeEvidenceArtifact（dict）。
    裸字符串 / 缺 verdict → NOT_PROVEN（不能传 "EVIDENCE_READY" 自证）。"""
    if not isinstance(evidence_artifact, dict):
        return "NOT_PROVEN"
    verdict = evidence_artifact.get("verdict")
    if verdict in ("CERTIFICATION_SUSPENDED", "NO_NEW_RISK"):
        return "RENEWAL_BLOCKED"
    if verdict in ("NOT_PROVEN", None, ""):
        return "NOT_PROVEN"
    if verdict in READY_VERDICTS:
        return "RENEWAL_ELIGIBLE"
    return "NOT_PROVEN"


# ---------------------------------------------------------------------------
# 正式构造入口：只能从真实 Ledger 生成 Evidence（禁止调用方裸 dict）
# ---------------------------------------------------------------------------

def _table_exists(conn, name) -> bool:
    r = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,)).fetchone()
    return bool(r)


def _has_column(conn, table, column) -> bool:
    try:
        cols = [r[1] for r in conn.execute(
            f"PRAGMA table_info({table})").fetchall()]
        return column in cols
    except Exception:
        return False


def _release_where(conn, table, alias="") -> str:
    """Release identity 过滤：优先 release_id 列；否则从 context JSON
    （真实台账的 release identity 存在 context.release_identity）。"""
    a = f"{alias}." if alias else ""
    if _has_column(conn, table, "release_id"):
        return f"{a}release_id=?"
    return f"json_extract({a}context,'$.release_identity.release_id')=?"


def build_runtime_evidence_from_ledger(conn, release_id, period,
                                       execution_mode="SHADOW",
                                       replay_result=None,
                                       today=None) -> dict:
    """从 Decision Ledger / Shadow Facts / Research Outcome / Replay /
    Runtime Event Ledger 构造正式 Runtime Evidence（决策支持六类核心）。

    缺必需表 → NOT_PROVEN（fail-closed）。
    replay_result 由 Daily Runner 传入（run_replay_evidence 结果）；
    未传入且无 REPLAY 事件 → replay NOT_PROVEN（Missing ≠ 0）。"""
    from datetime import datetime
    start, end = period["start"], period["end"]
    today = today or datetime.now().strftime("%Y-%m-%d")
    if not _table_exists(conn, "qcfp_decision_ledger"):
        return {"verdict": "NOT_PROVEN",
                "reason": "qcfp_decision_ledger 缺失",
                "evidence_hash": ""}
    if not _table_exists(conn, "qcfp_shadow_decision_fact"):
        return {"verdict": "NOT_PROVEN",
                "reason": "qcfp_shadow_decision_fact 缺失（Shadow "
                          "Terminal Facts 是决策支持核心证据）",
                "evidence_hash": ""}
    release_where = _release_where(conn, "qcfp_decision_ledger")
    actual = conn.execute(
        f"SELECT COUNT(DISTINCT stock_code) AS n "
        f"FROM qcfp_decision_ledger "
        f"WHERE {release_where} AND decision_date>=? AND decision_date<=? "
        "AND status='ACTIVE'",
        (release_id, start, end)).fetchone()["n"]
    expected = actual
    if _table_exists(conn, "qcfp_mtf_decision"):
        expected = conn.execute(
            "SELECT COUNT(DISTINCT stock_code) FROM qcfp_mtf_decision "
            "WHERE decision_date>=? AND decision_date<=?",
            (start, end)).fetchone()[0] or actual
    permission_violations = conn.execute(
        f"SELECT COUNT(*) AS n FROM qcfp_decision_ledger "
        f"WHERE {release_where} AND decision_date>=? AND decision_date<=? "
        "AND institutional_permission='BLOCK' AND final_target>"
        "COALESCE(previous_position,0)+0.000000001",
        (release_id, start, end)).fetchone()["n"]
    # Closure 6：pit_violations 从真实 PIT 事实列计算（不是硬编码 0）
    try:
        pit_rows = conn.execute(
            f"SELECT pit_grade, COUNT(*) AS n FROM qcfp_decision_ledger "
            f"WHERE {release_where} AND decision_date>=? "
            "AND decision_date<=? GROUP BY pit_grade",
            (release_id, start, end)).fetchall()
        pit_grade_dist = {r["pit_grade"] or "NULL": r["n"]
                          for r in pit_rows}
        pit_violations = sum(n for g, n in pit_grade_dist.items()
                             if g in ("E", "F", "NULL"))
    except Exception:
        return {"verdict": "NOT_PROVEN",
                "reason": "qcfp_decision_ledger.pit_grade 事实列缺失，"
                          "无法计算 PIT violations（fail-closed）",
                "evidence_hash": ""}
    # Shadow Terminal Facts（决策支持核心：safe_mode/halted 必须显式）
    terminal = {}
    for r in conn.execute(
            "SELECT terminal_state, COUNT(*) AS n "
            "FROM qcfp_shadow_decision_fact "
            "WHERE decision_date>=? AND decision_date<=? "
            "GROUP BY terminal_state",
            (start, end)).fetchall():
        terminal[r["terminal_state"] or "UNKNOWN"] = r["n"]
    # execution/reconciliation：决策支持模式下 OPTIONAL_SIMULATION_EVIDENCE
    if _table_exists(conn, "qcfp_runtime_event_ledger"):
        exec_section = _execution_from_events(
            conn, release_id, start, end, execution_mode)
        recon_section = _reconciliation_from_events(
            conn, release_id, start, end)
        recon_section.setdefault(
            "applicable", "OPTIONAL_SIMULATION_EVIDENCE")
        safety_section = _safety_from_events(
            conn, release_id, start, end)
        tail = conn.execute(
            "SELECT current_event_hash FROM qcfp_runtime_event_ledger "
            "ORDER BY event_seq DESC LIMIT 1").fetchone()
        runtime_chain_tail = tail[0] if tail else ""
    else:
        exec_section = {"applicable": "OPTIONAL_SIMULATION_EVIDENCE",
                        "reason": "无执行表（决策支持模式不需要 Broker）"}
        recon_section = {"applicable": "OPTIONAL_SIMULATION_EVIDENCE"}
        safety_section = {}
        runtime_chain_tail = ""
    # Replay section（P0-2 核心）：Daily Runner 传入 replay_result
    if replay_result is not None:
        replay_section = {
            "replay_total": int(replay_result.get("n_current_release")
                                or 0),
            "replay_eligible": int(replay_result.get("n_eligible") or 0),
            "replay_exact": int(replay_result.get("n_exact") or 0),
            "critical_replay_mismatch": int(
                replay_result.get("critical_mismatch") or 0),
            "replay_status": replay_result.get("status")
            or replay_result.get("replay_status")
            or ("REPLAY_PASS" if int(replay_result.get("n_exact") or 0)
                == int(replay_result.get("n_eligible") or 0)
                and int(replay_result.get("n_eligible") or 0) > 0
                else "REPLAY_NOT_PROVEN"),
        }
    elif _table_exists(conn, "qcfp_runtime_event_ledger"):
        safety_section = safety_section or _safety_from_events(
            conn, release_id, start, end)
        replay_section = {
            "replay_total": int(safety_section.get("replay_count") or 0),
            "replay_eligible": int(safety_section.get("replay_count") or 0),
            "replay_exact": int(safety_section.get("replay_count") or 0)
            - int(safety_section.get("critical_replay_mismatch") or 0),
            "critical_replay_mismatch": int(
                safety_section.get("critical_replay_mismatch") or 0),
            "replay_status": "REPLAY_PASS"
            if not safety_section.get("critical_replay_mismatch")
            and safety_section.get("replay_count") else
            "REPLAY_NOT_PROVEN",
        }
    else:
        replay_section = None
    # Outcome section（P0-2 核心）
    outcome_rows = []
    outcome_set_hash = ""
    if _table_exists(conn, "qcfp_research_outcome"):
        oc_cols = [r[1] for r in conn.execute(
            "PRAGMA table_info(qcfp_research_outcome)").fetchall()]
        if {"decision_date", "horizon", "horizon_end"} <= set(oc_cols):
            outcome_rows = conn.execute(
                "SELECT outcome_hash, horizon, horizon_end "
                "FROM qcfp_research_outcome "
                "WHERE release_id=? AND decision_date>=? "
                "AND decision_date<=?",
                (release_id, start, end)).fetchall()
            outcome_set_hash = hashlib.sha256(
                json.dumps(sorted(o["outcome_hash"] or "" for o in
                                  outcome_rows),
                           ensure_ascii=False).encode("utf-8")
            ).hexdigest()[:16]
    matured = {"5D": 0, "20D": 0, "60D": 0}
    for o in outcome_rows:
        h = str(o["horizon"] or "").upper()
        if h in matured and o["horizon_end"] \
                and str(o["horizon_end"])[:10] <= today:
            matured[h] += 1
    from ..research.decision_outcome import outcome_maturity_summary, \
        outcome_type_breakdown
    outcome_section = outcome_maturity_summary(
        [dict(o) for o in outcome_rows], expected, today=today)
    outcome_section["outcome_count"] = len(outcome_rows)
    outcome_section["outcome_coverage"] = outcome_section.get(
        "outcome_record_coverage", 0.0)
    oc_cols = [r[1] for r in conn.execute(
        "PRAGMA table_info(qcfp_research_outcome)").fetchall()] \
        if _table_exists(conn, "qcfp_research_outcome") else []
    if {"future_return", "outcome_type"} <= set(oc_cols):
        typed_rows = conn.execute(
            "SELECT outcome_type, future_return "
            "FROM qcfp_research_outcome "
            "WHERE release_id=? AND decision_date>=? "
            "AND decision_date<=?",
            (release_id, start, end)).fetchall()
        outcome_section["outcome_type_breakdown"] = \
            outcome_type_breakdown([dict(r) for r in typed_rows])
    else:
        outcome_section["outcome_type_breakdown"] = {}
    # Stability section（P0-2 核心：flip rate / duplicates）
    dl_cols = [r[1] for r in conn.execute(
        "PRAGMA table_info(qcfp_decision_ledger)").fetchall()]
    has_stability_cols = {"final_target", "next_fsm_state"} <= set(dl_cols)
    has_run_id = "run_id" in dl_cols
    run_id_expr = "run_id" if has_run_id else "'' AS run_id"
    raw_decision_rows = conn.execute(
        f"SELECT id, {run_id_expr}, "
        f"decision_id, stock_code, decision_date, "
        f"final_target, next_fsm_state FROM qcfp_decision_ledger "
        f"WHERE {release_where} AND decision_date>=? "
        "AND decision_date<=? AND status='ACTIVE'",
        (release_id, start, end)).fetchall() \
        if has_stability_cols else conn.execute(
        f"SELECT id, {run_id_expr}, "
        f"decision_id, stock_code, decision_date, "
        f"final_target, '' AS next_fsm_state FROM qcfp_decision_ledger "
        f"WHERE {release_where} AND decision_date>=? "
        "AND decision_date<=? AND status='ACTIVE'",
        (release_id, start, end)).fetchall()
    # 同 (stock, date) 多 run 重跑：取最新 ACTIVE 决策为当日事实
    latest = {}
    for r in raw_decision_rows:
        key = (r["stock_code"], r["decision_date"])
        if key not in latest or r["id"] > latest[key]["id"]:
            latest[key] = r
    decision_rows = list(latest.values())
    # 重复决策 = 同一 run_id 内 (stock,date) 重复行数（历史重跑不计）
    duplicate_decisions = 0
    run_groups = {}
    for r in raw_decision_rows:
        run_groups.setdefault(r["run_id"] or "", []).append(
            (r["stock_code"], r["decision_date"]))
    for key_rows in run_groups.values():
        duplicate_decisions += max(
            0, len(key_rows) - len(set(key_rows)))
    flips = 0
    prev_sql = (
        "SELECT final_target, next_fsm_state "
        "FROM qcfp_decision_ledger "
        "WHERE stock_code=? AND decision_date<? "
        "AND status='ACTIVE' "
        "ORDER BY decision_date DESC, id DESC LIMIT 1"
        if has_stability_cols else
        "SELECT final_target, '' AS next_fsm_state "
        "FROM qcfp_decision_ledger "
        "WHERE stock_code=? AND decision_date<? "
        "AND status='ACTIVE' "
        "ORDER BY decision_date DESC, id DESC LIMIT 1")
    for r in decision_rows:
        prev = conn.execute(prev_sql, (r["stock_code"], start)).fetchone()
        if prev is None:
            continue
        cur_t = float(r["final_target"] or 0.0)
        prev_t = float(prev["final_target"] or 0.0)
        if (cur_t * prev_t < 0) or (r["next_fsm_state"]
                                    != prev["next_fsm_state"]):
            flips += 1
    stability_section = {
        "decision_flip_rate": round(flips / len(decision_rows), 4)
        if decision_rows else 0.0,
        "duplicate_decisions": duplicate_decisions,
    }
    # Data Quality section（P0-2 核心）
    dq_dist = {}
    try:
        for r in conn.execute(
                f"SELECT data_quality, COUNT(*) AS n "
                f"FROM qcfp_decision_ledger "
                f"WHERE {release_where} AND decision_date>=? "
                "AND decision_date<=? GROUP BY data_quality",
                (release_id, start, end)).fetchall():
            dq_dist[r["data_quality"] or "NULL"] = r["n"]
    except Exception:
        dq_dist = {}
    data_quality_section = {
        "pit_grade_distribution": pit_grade_dist,
        "data_quality_distribution": dq_dist,
    }
    risk_section = {"max_drawdown": None}
    if _table_exists(conn, "qcfp_research_outcome"):
        outcome_rows = conn.execute(
            "SELECT outcome_hash FROM qcfp_research_outcome "
            "WHERE release_id=?", (release_id,)).fetchall()
        outcome_set_hash = hashlib.sha256(
            json.dumps(sorted(o["outcome_hash"] or "" for o in
                              outcome_rows),
                       ensure_ascii=False).encode("utf-8")
        ).hexdigest()[:16]
        outcome_count = len(outcome_rows)
    else:
        outcome_set_hash, outcome_count = "", 0
    decision_chain_tail = ""
    try:
        tail = conn.execute(
            "SELECT current_hash FROM qcfp_decision_ledger "
            "ORDER BY id DESC LIMIT 1").fetchone()
        decision_chain_tail = tail[0] if tail else ""
    except Exception:
        try:
            tail = conn.execute(
                "SELECT context FROM qcfp_decision_ledger "
                "ORDER BY id DESC LIMIT 1").fetchone()
            if tail and tail["context"]:
                decision_chain_tail = (json.loads(tail["context"]).get(
                    "ledger_chain") or {}).get("current_ledger_hash", "")
        except Exception:
            decision_chain_tail = ""
    decision_section = {
        "expected_decisions": int(expected),
        "actual_decisions": int(actual),
        "coverage": round(actual / expected, 4) if expected else 1.0,
        "permission_violations": int(permission_violations),
        "uncertified_executions": int(exec_section.get(
            "uncertified_count", 0)),
        "pit_violations": int(pit_violations),
        "safe_mode_count": int(terminal.get("SAFE_MODE") or 0),
        "halted_count": int(terminal.get("HALTED") or 0),
    }
    artifact = runtime_evidence_artifact(
        identity={"release_id": release_id},
        period=period,
        decision=decision_section,
        replay=replay_section,
        outcome=outcome_section,
        stability=stability_section,
        data_quality=data_quality_section,
        risk=risk_section,
        execution=exec_section,
        reconciliation=recon_section,
        safety=safety_section,
        opportunity={"outcome_count": outcome_count},
        execution_mode=execution_mode)
    if artifact["verdict"] == "NOT_PROVEN":
        return artifact
    artifact["ledger_bindings"] = {
        "decision_ledger_chain_tail": decision_chain_tail,
        "runtime_event_chain_tail": runtime_chain_tail,
        "outcome_set_hash": outcome_set_hash,
        "replay_hash": (replay_result or {}).get(
            "settings_registry_hash", "")
        or (replay_result or {}).get("replay_hash", "")
        or safety_section.get("replay_hash", ""),
    }
    raw = json.dumps({"evidence": artifact["evidence"],
                      "ledger_bindings": artifact["ledger_bindings"]},
                     sort_keys=True, ensure_ascii=False, default=str)
    artifact["evidence_hash"] = hashlib.sha256(
        raw.encode("utf-8")).hexdigest()[:16]
    artifact["source"] = "ledger_only"
    return artifact


def _execution_from_events(conn, release_id, start, end,
                           execution_mode):
    from ..execution.unknown_resolution import \
        unknown_resolution_metrics_from_events

    def _count(etype):
        r = conn.execute(
            "SELECT COUNT(*) AS n FROM qcfp_runtime_event_ledger "
            "WHERE release_id=? AND event_type=? "
            "AND substr(event_time,1,10)>=? "
            "AND substr(event_time,1,10)<=?",
            (release_id, etype, start, end)).fetchone()
        return r["n"]
    unresolved_unknown = conn.execute(
        "SELECT COUNT(*) AS n FROM qcfp_runtime_event_ledger e "
        "WHERE e.release_id=? AND e.event_type='ORDER_UNKNOWN' "
        "AND substr(e.event_time,1,10)>=? "
        "AND substr(e.event_time,1,10)<=? AND NOT EXISTS ("
        "SELECT 1 FROM qcfp_runtime_event_ledger r "
        "WHERE r.release_id=e.release_id "
        "AND r.event_type='RECONCILIATION' "
        "AND r.broker_order_id=e.broker_order_id AND r.event_seq>e.event_seq "
        "AND r.reconciliation_status='IN_SYNC')",
        (release_id, start, end)).fetchone()["n"]
    unk = unknown_resolution_metrics_from_events(
        conn, release_id, start, end)
    uncertified_count = conn.execute(
        "SELECT COUNT(DISTINCT decision_id) AS n "
        "FROM qcfp_runtime_event_ledger "
        "WHERE release_id=? AND event_type IN "
        "('ORDER_SENT','FILL','PARTIAL_FILL') "
        "AND substr(event_time,1,10)>=? "
        "AND substr(event_time,1,10)<=? "
        "AND (certificate_id IS NULL OR certificate_id='')",
        (release_id, start, end)).fetchone()["n"]
    if execution_mode == "SHADOW":
        return {"applicable": "OPTIONAL_SIMULATION_EVIDENCE"}
    return {
        "applicable": "REQUIRED",
        "order_intents": _count("ORDER_INTENT"),
        "orders_sent": _count("ORDER_SENT"),
        "fills": _count("FILL"),
        "partial_fills": _count("PARTIAL_FILL"),
        "rejects": _count("ORDER_REJECT"),
        "unknown_count": _count("ORDER_UNKNOWN"),
        "resolved_unknown": int(unk.get("resolved_unknown") or 0),
        "unresolved_unknown": int(unk.get("unresolved_unknown")
                                  or unresolved_unknown),
        "query_attempt_count": int(unk.get("query_attempt_count") or 0),
        "blind_resend_count": int(unk.get("blind_resend_count") or 0),
        "resolution_latency_ms": unk.get("resolution_latency_ms"),
        "max_resolution_latency": unk.get("max_resolution_latency"),
        "uncertified_count": uncertified_count,
    }


def _reconciliation_from_events(conn, release_id, start, end):
    rows = conn.execute(
        "SELECT reconciliation_status, COUNT(*) AS n "
        "FROM qcfp_runtime_event_ledger WHERE release_id=? "
        "AND event_type='RECONCILIATION' "
        "AND substr(event_time,1,10)>=? "
        "AND substr(event_time,1,10)<=? GROUP BY reconciliation_status",
        (release_id, start, end)).fetchall()
    counts = {r["reconciliation_status"] or "UNKNOWN": r["n"]
              for r in rows}
    actual = sum(counts.values())
    # Closure 6：Expected 来自 eligible Order/Position 事件集合，
    # Actual 来自 RECONCILIATION 事件集合——两者必须来自不同事实集合，
    # 不能 expected=actual 自证 100%。
    expected = conn.execute(
        "SELECT COUNT(*) AS n FROM qcfp_runtime_event_ledger "
        "WHERE release_id=? AND event_type IN "
        "('ORDER_SENT','FILL','PARTIAL_FILL','ORDER_UNKNOWN',"
        "'BROKER_POSITION') "
        "AND substr(event_time,1,10)>=? AND substr(event_time,1,10)<=?",
        (release_id, start, end)).fetchone()["n"]
    return {
        "expected_reconciliations": expected,
        "actual_reconciliations": actual,
        "coverage": round(actual / expected, 4) if expected else 1.0,
        "mismatch": counts.get("MISMATCH", 0),
        "unknown": counts.get("UNKNOWN", 0),
        "unresolved_mismatch": counts.get("MISMATCH", 0),
    }


def _safety_from_events(conn, release_id, start, end):
    def _count(etype):
        r = conn.execute(
            "SELECT COUNT(*) AS n FROM qcfp_runtime_event_ledger "
            "WHERE release_id=? AND event_type=? "
            "AND substr(event_time,1,10)>=? "
            "AND substr(event_time,1,10)<=?",
            (release_id, etype, start, end)).fetchone()
        return r["n"]
    replay_hash = ""
    rp = conn.execute(
        "SELECT payload FROM qcfp_runtime_event_ledger "
        "WHERE release_id=? AND event_type='REPLAY' "
        "AND substr(event_time,1,10)>=? "
        "AND substr(event_time,1,10)<=? ORDER BY event_seq DESC LIMIT 1",
        (release_id, start, end)).fetchone()
    if rp and rp["payload"]:
        try:
            replay_hash = json.loads(rp["payload"]).get("replay_hash", "")
        except Exception:
            replay_hash = ""
    # Closure 6：critical_replay_mismatch 从 REPLAY 事件事实计算
    replay_rows = conn.execute(
        "SELECT payload FROM qcfp_runtime_event_ledger "
        "WHERE release_id=? AND event_type='REPLAY' "
        "AND substr(event_time,1,10)>=? "
        "AND substr(event_time,1,10)<=?",
        (release_id, start, end)).fetchall()
    critical_replay_mismatch = 0
    for rr in replay_rows:
        try:
            if json.loads(rr["payload"] or "{}").get("verified") is False:
                critical_replay_mismatch += 1
        except Exception:
            critical_replay_mismatch += 1   # payload 不可解析 → 视为 mismatch
    return {
        "incident_count": _count("INCIDENT"),
        "recovery_count": _count("RECOVERY"),
        "replay_count": _count("REPLAY"),
        "critical_replay_mismatch": critical_replay_mismatch,
        "reactivation_count": _count("REACTIVATION"),
        "replay_hash": replay_hash,
    }
