# coding: utf-8
"""Critical Path Observability（QCFP-MTF 2.8：57 号关键路径可观测性）

只监控真正影响决策的 Canonical 链路（不建巨型监控平台）：
    Evidence available → PIT valid → Permission generated → Wave generated
    → Governance finalized → Snapshot committed → Ledger hash committed
    → Execution instruction generated

每步记录 latency / status / version / input-output hash；
目标：某天没有产生 Decision 时能立即定位卡在哪一步。
"""


CRITICAL_PATH = (
    ("evidence_available", "EVIDENCE"),
    ("pit_valid", "PIT"),
    ("permission_generated", "PERMISSION"),
    ("wave_generated", "WAVE"),
    ("governance_finalized", "GOVERNANCE"),
    ("snapshot_committed", "SNAPSHOT"),
    ("ledger_hash_committed", "LEDGER"),
    ("execution_instruction_generated", "EXECUTION"),
)


def critical_path_observability(steps: dict) -> dict:
    """steps：{stage: {"status", "latency_ms", "version", "io_hash"}}。"""
    path, first_blocker = [], None
    for stage, layer in CRITICAL_PATH:
        info = steps.get(stage) or {}
        status = info.get("status") or "MISSING"
        path.append({
            "stage": stage, "layer": layer, "status": status,
            "latency_ms": info.get("latency_ms"),
            "version": info.get("version"),
            "io_hash": info.get("io_hash"),
        })
        if first_blocker is None and status != "OK":
            first_blocker = stage
    layer_of = dict(CRITICAL_PATH)
    hint = ("决策链完整" if not first_blocker
            else f"决策链停在 {first_blocker}（{layer_of[first_blocker]}）")
    return {"path": path, "first_blocker": first_blocker,
            "all_ok": first_blocker is None,
            "locatable": True, "hint": hint}


def critical_path_from_snapshot(snap, ledger_ok=True,
                                execution_ok=False) -> dict:
    """新 16 号：由真实 DecisionSnapshot 自动发出 8 段 stage event。

    不再人工拼 metrics；缺失关键 stage 本身也算异常。
    """
    ctx = getattr(snap, "context", None) or {}
    proof = (ctx.get("governance_proof") or {})
    pit = getattr(snap, "pit_grade", "") or ""
    steps = {
        "evidence_available": {"status": "OK", "version": "evidence",
                               "io_hash": getattr(
                                   snap, "input_fingerprint", "")},
        "pit_valid": {"status": "OK" if pit in ("A", "B")
                      else "FAIL",
                      "version": f"pit_{pit}",
                      "io_hash": ""},
        "permission_generated": {
            "status": "OK" if getattr(snap, "institutional_permission",
                                      "") else "FAIL",
            "version": getattr(snap, "institutional_permission", ""),
            "io_hash": ""},
        "wave_generated": {
            "status": "OK" if getattr(snap, "wave_stage", "")
            else "SKIP",   # 无 Wave 证据 = 机会层未参与（不算失败）
            "version": getattr(snap, "wave_stage", ""),
            "io_hash": ""},
        "governance_finalized": {
            "status": "OK" if proof.get("proof") == "PASS"
            else "FAIL",
            "version": getattr(snap, "rule_version", ""),
            "io_hash": getattr(snap, "binding_constraint", "")},
        "snapshot_committed": {
            "status": "OK" if getattr(snap, "decision_id", "")
            else "FAIL",
            "version": getattr(snap, "schema_version", ""),
            "io_hash": getattr(snap, "input_fingerprint", "")},
        "ledger_hash_committed": {
            "status": "OK" if ledger_ok else "FAIL",
            "version": getattr(snap, "run_id", ""),
            "io_hash": ""},
        "execution_instruction_generated": {
            "status": "OK" if execution_ok else "PENDING",
            "version": "",
            "io_hash": ""},
    }
    return critical_path_observability(steps)


def decision_layer_outcome(snap, ledger_ok=True) -> dict:
    """新 57 号：任何 CertifiedDecision / NO_TRADE / ABSTAIN 都能回答
    到底在哪一层被通过或过滤，而不是笼统说"今天没信号"。"""
    path = critical_path_from_snapshot(snap, ledger_ok=ledger_ok,
                                       execution_ok=True)
    blocker = path.get("first_blocker")
    target = float(getattr(snap, "target_position", 0.0) or 0.0)
    if blocker:
        layer = dict(CRITICAL_PATH)[blocker]
        return {"outcome": "FILTERED",
                "filtered_at": blocker,
                "layer": layer,
                "reason": f"停在第 {blocker} 层（{layer}）",
                "critical_path": path}
    if target > 1e-9:
        return {"outcome": "CERTIFIED_DECISION",
                "filtered_at": None,
                "layer": "EXECUTION",
                "reason": "全部层通过",
                "critical_path": path}
    return {"outcome": "NO_TRADE",
            "filtered_at": None,
            "layer": "FINAL_TARGET",
            "reason": "可信判断：现在没有值得参与的机会",
            "critical_path": path}


def build_runtime_critical_path(stage_events) -> dict:
    """Release 2（新 17 号）：真实 Runtime 事件（非事后从 Snapshot 猜）。

    stage_events：{stage: {"status", "latency_ms", "version",
    "input_hash", "output_hash", "reason"}}
    注意：SKIPPED ≠ MISSING——SKIPPED 不阻塞，MISSING 算异常。
    """
    steps = {}
    for stage, layer in CRITICAL_PATH:
        ev = (stage_events or {}).get(stage)
        if ev is None:
            steps[stage] = {"status": "MISSING"}
            continue
        status = str(ev.get("status") or "MISSING").upper()
        steps[stage] = {
            "status": status,
            "latency_ms": ev.get("latency_ms"),
            "version": ev.get("version"),
            "io_hash": f"{ev.get('input_hash')}->{ev.get('output_hash')}",
            "reason": ev.get("reason", ""),
        }
    path = critical_path_observability(steps)
    # SKIPPED 不阻塞（例如 Wave 无证据 → FSM/Governance 可跳过）
    for entry in path["path"]:
        if entry["status"] == "SKIPPED" \
                and path["first_blocker"] == entry["stage"]:
            path["first_blocker"] = None
    path["all_ok"] = path["first_blocker"] is None
    return path


def decision_critical_path_trace(snapshot, stage_events) -> dict:
    """任何 CertifiedDecision / NO_TRADE / ABSTAIN / DECISION_HALTED
    都必须生成完整 CriticalPathTrace。"""
    path = build_runtime_critical_path(stage_events)
    return {"decision_id": getattr(snapshot, "decision_id", ""),
            "critical_path_trace": path,
            "answer": path.get("hint")}
