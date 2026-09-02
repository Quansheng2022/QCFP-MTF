# coding: utf-8
"""Paper Order Pipeline（Runtime Evidence Wiring：第 5/6 项）

状态：OPTIONAL_SIMULATION_EVIDENCE / RESEARCH_ONLY（P0-3 目标重新对齐）
正式入口迁移到 research/decision_outcome.py；本模块的 Order/Fill/
Position 模拟仅作研究/仿真支持，不再作为 Production Qualification
authority。

复用现有 OrderStateMachine + Simulator + PositionReconciliation：
    DecisionSnapshot → Execution Eligibility → OrderIntent（差额）→
    OSM.send() → Simulator → ACK/PARTIAL/FILLED/REJECTED/UNKNOWN →
    Paper Position → Event/EOD Reconciliation → Execution Calibration

没有第二 Execution Authority；Simulator 只能减小/延迟/加成本，不能
重新计算 FinalTarget。evidence_source = PAPER_PROXY。

Runtime Evidence Wiring 修改：
    * 唯一 Status Mapping：
        FILLED→ack(full) / PARTIAL→ack(partial) / REJECTED→reject() /
        CANCELLED→cancel() / UNKNOWN→timeout() / 未知→timeout()
      UNKNOWN 永远不会变成 ACK；禁止盲重发；
    * 每个订单事件（SENT/ACK/FILL/REJECT/UNKNOWN/RECONCILIATION）
      先落 Runtime Event Ledger（conn 提供时）；
    * EOD Reconciliation：broker_position 缺失 → UNKNOWN（绝不拿
      internal 伪装一致）；coverage = matched/expected；
      unexpected_broker_positions 单独报告；
    * Calibration 接线：每次 Paper Fill 保存 estimated/realized
      slippage·fill_ratio·exit_days·participation 到事件 payload，
      供 execution_calibration_report 聚合（禁止自动改参数）。
"""

from .order_state_machine import OrderStateMachine, position_reconciliation
from .execution_context import (ExecutionContext, canonical_target_of,
                                decision_identity_of)


# Simulator Status → OSM Transition（第 5 项唯一映射）
SIMULATOR_STATUS_MAP = {
    "FILLED": "ack_full",
    "PARTIAL": "ack_partial",
    "REJECTED": "reject",
    "CANCELLED": "cancel",
    "UNKNOWN": "timeout",
}


def map_simulator_status(status: str) -> str:
    """未知 Status（如 BROKER_PENDING_X）→ UNKNOWN/timeout，
    绝不默认 ACK。"""
    key = str(status or "").upper()
    return SIMULATOR_STATUS_MAP.get(key, "timeout")


def order_intent(current_position, deployment_target) -> dict:
    """OrderIntent 从差额产生：Current vs Deployment/Executable Target。"""
    cur = float(current_position or 0.0)
    target = float(deployment_target or 0.0)
    delta = round(target - cur, 4)
    return {"current_position": round(cur, 4),
            "deployment_target": round(target, 4),
            "delta": delta,
            "side": "BUY" if delta > 1e-9 else
            "SELL" if delta < -1e-9 else "NONE",
            "quantity": abs(delta),
            "rule": "OrderIntent 是差额，不是把目标当新买单"}


def paper_order_pipeline(decision_snapshot, context: ExecutionContext,
                         current_position, simulator, conn=None,
                         event_time="") -> dict:
    """Paper 完整流水线（一次下单 + 模拟成交 + 事件级 Reconcile）。"""
    if context.execution_mode != "PAPER":
        return {"error": "paper pipeline 只接受 PAPER mode"}
    target = canonical_target_of(decision_snapshot)
    identity = decision_identity_of(decision_snapshot)
    intent = order_intent(current_position, target)
    if intent["side"] == "NONE":
        if conn is not None:
            from .runtime_event_ledger import append_runtime_event
            append_runtime_event(conn, {
                "event_id": f"INT-{identity['decision_id']}",
                "event_type": "ORDER_INTENT",
                "event_time": event_time,
                "decision_id": identity["decision_id"],
                "release_id": identity["release_id"],
                "execution_mode": "PAPER",
                "account_id": getattr(context, "account_id", ""),
                "stock_code": identity["stock_code"],
                "side": "NONE",
                "requested_qty": 0.0,
                "payload": {"intent": intent,
                            "rule": "无差额 → 无订单"}})
        return {"intent": intent, "order": None,
                "evidence_source": "PAPER_PROXY",
                "reconciliation": position_reconciliation(
                    target, current_position, current_position)}
    osm = OrderStateMachine()
    order_id = f"P-{identity['decision_id']}"
    sent = osm.send(order_id, intent["quantity"])
    if conn is not None:
        from .runtime_event_ledger import append_runtime_event
        append_runtime_event(conn, {
            "event_id": f"OS-{order_id}",
            "event_type": "ORDER_SENT",
            "event_time": event_time,
            "decision_id": identity["decision_id"],
            "release_id": identity["release_id"],
            "execution_mode": "PAPER",
            "account_id": getattr(context, "account_id", ""),
            "stock_code": identity["stock_code"],
            "order_intent_id": order_id,
            "side": intent["side"],
            "requested_qty": intent["quantity"],
            "payload": {"intent": intent}})
    sim = simulator.execute_order(intent) if simulator else \
        {"status": "UNKNOWN"}
    status = sim.get("status", "UNKNOWN")
    transition = map_simulator_status(status)
    fill = sim.get("filled_qty")
    if transition == "ack_full":
        ack = osm.ack(order_id, fill=fill)
    elif transition == "ack_partial":
        ack = osm.ack(order_id, fill=fill)
    elif transition == "reject":
        ack = osm.reject(order_id, reason=sim.get("reason", ""))
    elif transition == "cancel":
        ack = osm.cancel(order_id)
    else:  # timeout / unknown status
        ack = osm.timeout(order_id)
    # Closure：Internal 与 Broker Position 独立维护——
    # internal 按成交更新，broker 来自 Simulator，两者可 mismatch。
    filled = float(fill or 0.0)
    new_internal = float(current_position or 0.0) + \
        (filled if intent["side"] == "BUY" else -filled)
    broker_pos = sim.get("position")
    recon = position_reconciliation(target, new_internal, broker_pos)
    calibration = _fill_calibration_sample(intent, sim)
    event_type = {
        "ack_full": "FILL", "ack_partial": "PARTIAL_FILL",
        "reject": "ORDER_REJECT", "cancel": "ORDER_CANCEL",
    }.get(transition, "ORDER_UNKNOWN")
    if conn is not None:
        from .runtime_event_ledger import append_runtime_event
        append_runtime_event(conn, {
            "event_id": f"OA-{order_id}",
            "event_type": event_type,
            "event_time": event_time,
            "decision_id": identity["decision_id"],
            "release_id": identity["release_id"],
            "execution_mode": "PAPER",
            "account_id": getattr(context, "account_id", ""),
            "stock_code": identity["stock_code"],
            "order_intent_id": order_id,
            "side": intent["side"],
            "requested_qty": intent["quantity"],
            "filled_qty": fill,
            "internal_position": new_internal,
            "broker_position": broker_pos,
            "reconciliation_status": recon["status"],
            "payload": {"ack_state": ack["state"],
                        "simulator_status": status,
                        "calibration": calibration}})
        append_runtime_event(conn, {
            "event_id": f"RC-{order_id}",
            "event_type": "RECONCILIATION",
            "event_time": event_time,
            "decision_id": identity["decision_id"],
            "release_id": identity["release_id"],
            "execution_mode": "PAPER",
            "account_id": getattr(context, "account_id", ""),
            "stock_code": identity["stock_code"],
            "order_intent_id": order_id,
            "internal_position": new_internal,
            "broker_position": broker_pos,
            "reconciliation_status": recon["status"],
            "payload": {"reconciliation": recon}})
    return {
        "intent": intent,
        "order": {"order_id": order_id, "side": intent["side"],
                  "quantity": intent["quantity"],
                  "order_state": ack["state"]},
        "order_state": sent["state"],
        "simulator_result": sim,
        "ack_state": ack["state"],
        "position": broker_pos,
        "reconciliation": recon,
        "calibration_sample": calibration,
        "evidence_source": "PAPER_PROXY",
        "status_transition": transition,
        "rule": "Paper 不是 Broker Truth；PAPER_PROXY ≠ BROKER_REAL",
    }


def _fill_calibration_sample(intent, sim) -> dict:
    """每次 Paper Fill 保存 estimated/realized 执行假设样本
    （第 6 项：Calibration 接线；禁止自动改参数）。"""
    requested = float(intent.get("quantity") or 0.0)
    filled = float(sim.get("filled_qty") or 0.0)
    fill_ratio = round(filled / requested, 4) if requested else 1.0
    estimated_slippage = float(sim.get("estimated_slippage_bps")
                               or 0.0)
    realized_slippage = float(sim.get("slippage_bps") or 0.0)
    return {
        "estimated_slippage": estimated_slippage,
        "realized_slippage": realized_slippage,
        "estimated_fill_ratio": float(sim.get("fill_rate") or 1.0),
        "realized_fill_ratio": fill_ratio,
        "estimated_exit_days": float(sim.get("exit_delay_days") or 0.0),
        "realized_exit_days": float(sim.get("realized_exit_days")
                                    or 0.0),
        "estimated_participation": float(sim.get("participation_rate")
                                         or 0.0),
        "realized_participation": fill_ratio,
    }


def paper_calibration_samples(events: list) -> dict:
    """从 Runtime Event payload 聚合 Calibration 样本
    （execution_calibration_report 消费）。"""
    from ..monitoring.execution_calibration import \
        execution_calibration_report
    samples = []
    for ev in events or []:
        payload = ev.get("payload") or {}
        cal = payload.get("calibration") or {}
        if not cal:
            continue
        for dim, est_key, real_key in (
                ("slippage", "estimated_slippage", "realized_slippage"),
                ("fill_ratio", "estimated_fill_ratio",
                 "realized_fill_ratio"),
                ("exit_days", "estimated_exit_days",
                 "realized_exit_days"),
                ("participation", "estimated_participation",
                 "realized_participation")):
            samples.append({"dimension": dim,
                            "estimated": cal.get(est_key),
                            "realized": cal.get(real_key)})
    return execution_calibration_report(samples)


def paper_daily_reconciliation(paper_records, canonical_targets,
                               order_records=None, fill_records=None,
                               fee_records=None) -> dict:
    """EOD Reconciliation：Internal vs Paper Broker，覆盖 100%。

    Runtime Evidence Wiring（第 6 项）：
    * broker_position 缺失 → UNKNOWN（绝不拿 internal 伪装一致）；
    * coverage = matched / expected（canonical_targets keys）；
    * unexpected_broker_positions 单独报告。

    P0-5：独立 5 层对账（Decision / Order / Fill / Position / Cash-Fee）。
    Expected 与 Actual 必须来自独立事实集合：
        Decision 层 ← Decision Ledger canonical_targets
        Order/Fill/Position/Cash-Fee 层 ← Broker/Event 事实
    每层只允许 MATCHED / MISMATCH / UNKNOWN / NOT_APPLICABLE。"""
    results = {}
    expected = set(canonical_targets)
    unexpected = [c for c in paper_records if c not in expected]
    matched = 0
    for code in expected:
        target = canonical_targets.get(code, 0.0)
        rec = paper_records.get(code) or {}
        internal = rec.get("position", 0.0)
        broker = rec.get("broker_position")      # 禁止 fallback to internal
        results[code] = position_reconciliation(target, internal, broker)
        if results[code]["status"] in ("IN_SYNC", "PARTIAL", "MISMATCH",
                                       "UNKNOWN"):
            matched += 1
    coverage = round(matched / max(len(expected), 1), 4)
    # ---- P0-5：5 层独立对账（每层状态来自不同事实集合）----
    layers = {
        "decision": _layer_decision(len(expected), matched, coverage),
        "order": _layer_order(expected, order_records),
        "fill": _layer_fill(expected, fill_records, paper_records),
        "position": _layer_position(results),
        "cash_fee": _layer_cash_fee(expected, fee_records),
    }
    return {"results": results,
            "layers": layers,
            "reconciliation_status": _aggregate_layer_status(layers),
            "reconciliation_coverage": coverage,
            "expected_reconciliations": len(expected),
            "actual_reconciliations": matched,
            "unresolved_unknown": sum(
                1 for r in results.values() if r["status"] == "UNKNOWN"),
            "unresolved_mismatch": sum(
                1 for r in results.values() if r["status"] == "MISMATCH"),
            "unexpected_broker_positions": sorted(unexpected),
            "rule": "缺 Broker Position → UNKNOWN；coverage 只统计 "
                    "expected symbols；5 层对账各自来自独立事实集合"}


def _layer_decision(n_expected, n_matched, coverage) -> dict:
    if n_expected == 0:
        return {"status": "NOT_APPLICABLE", "expected": 0,
                "matched": 0, "reason": "无 canonical 决策"}
    status = "MATCHED" if coverage >= 1.0 - 1e-9 else "MISMATCH"
    return {"status": status, "expected": n_expected,
            "matched": n_matched}


def _layer_order(expected, order_records) -> dict:
    if order_records is None:
        return {"status": "NOT_APPLICABLE",
                "reason": "无 order-layer 独立事实"}
    missing = [c for c in expected
               if not (order_records.get(c) or {}).get("broker_order_id")]
    if missing:
        return {"status": "MISMATCH", "expected": len(expected),
                "missing_orders": sorted(missing)}
    return {"status": "MATCHED", "expected": len(expected)}


def _layer_fill(expected, fill_records, paper_records) -> dict:
    if fill_records is None:
        # 退化为 broker_position 可观测性（仍独立于 internal）
        missing = [c for c in expected
                   if (paper_records.get(c) or {}).get(
                       "broker_position") is None]
        if missing:
            return {"status": "UNKNOWN",
                    "missing_broker_positions": sorted(missing)}
        return {"status": "MATCHED", "expected": len(expected)}
    missing = [c for c in expected
               if (fill_records.get(c) or {}).get("filled_qty") is None]
    if missing:
        return {"status": "UNKNOWN",
                "missing_fills": sorted(missing)}
    return {"status": "MATCHED", "expected": len(expected)}


def _layer_position(results) -> dict:
    if not results:
        return {"status": "NOT_APPLICABLE"}
    statuses = [r["status"] for r in results.values()]
    if "UNKNOWN" in statuses:
        return {"status": "UNKNOWN", "unknown": statuses.count("UNKNOWN")}
    if "MISMATCH" in statuses:
        return {"status": "MISMATCH",
                "mismatch": statuses.count("MISMATCH")}
    return {"status": "MATCHED", "checked": len(statuses)}


def _layer_cash_fee(expected, fee_records) -> dict:
    if not fee_records:
        return {"status": "NOT_APPLICABLE",
                "reason": "无 fee-layer 独立事实"}
    mismatches = []
    for code in expected:
        f = fee_records.get(code) or {}
        est, real = f.get("estimated_fee"), f.get("realized_fee")
        if est is None or real is None:
            mismatches.append({"stock_code": code,
                               "reason": "fee 缺失"})
            continue
        if abs(float(est) - float(real)) > 1e-6:
            mismatches.append({"stock_code": code, "estimated": est,
                               "realized": real})
    if mismatches:
        return {"status": "MISMATCH", "mismatches": mismatches[:10]}
    return {"status": "MATCHED", "checked": len(expected)}


def _aggregate_layer_status(layers) -> str:
    """层聚合：任一 MISMATCH → MISMATCH；否则任一 UNKNOWN → UNKNOWN；
    其余（含全 NOT_APPLICABLE）→ MATCHED。"""
    statuses = [l.get("status") for l in layers.values()]
    if "MISMATCH" in statuses:
        return "MISMATCH"
    if "UNKNOWN" in statuses:
        return "UNKNOWN"
    return "MATCHED"
