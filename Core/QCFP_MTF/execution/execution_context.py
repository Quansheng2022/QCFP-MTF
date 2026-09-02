# coding: utf-8
"""ExecutionContext / execution_mode（Runtime Evidence Wiring：第 1 项）

execution_mode 只允许 SHADOW / PAPER / SMALL_LIVE，回答
"Canonical Decision 做到哪个执行层？"，绝不回答"该不该买"。

铁律：execution_mode 是 Operational Context，不是 Canonical Decision
Input——禁止进入 Permission/Wave/FSM/FinalTarget/CanonicalAction/
DecisionPathHash。同样 Evidence+Release 下三种 mode 必须得到完全相同
的 Canonical Decision；只有 ExecutionEvent/DeploymentTarget/
ActualPosition 允许不同。

Runtime Evidence Wiring（第 1 项）：`dispatch_runtime()` 是唯一 Runtime
Dispatcher——Canonical evaluate 只执行一次，三种 mode 只改变 Execution 层。
deployment_cap 改为 Optional[float]=None：SHADOW/PAPER 不适用时为 None，
SMALL_LIVE 必填；0.0 不再用来伪装「未配置」。
"""

from dataclasses import dataclass
from typing import Optional


EXECUTION_MODES = ("SHADOW", "PAPER", "SMALL_LIVE")


@dataclass(frozen=True)
class ExecutionContext:
    execution_mode: str = "SHADOW"
    run_id: str = ""
    account_id: str = ""
    deployment_cap: Optional[float] = None
    broker_name: str = ""

    def as_dict(self) -> dict:
        return {"execution_mode": self.execution_mode,
                "run_id": self.run_id, "account_id": self.account_id,
                "deployment_cap": self.deployment_cap,
                "broker_name": self.broker_name}


def validate_execution_mode(mode: str) -> dict:
    m = str(mode or "").upper()
    if m not in EXECUTION_MODES:
        return {"execution_mode": m, "valid": False,
                "allowed": list(EXECUTION_MODES)}
    return {"execution_mode": m, "valid": True,
            "allowed": list(EXECUTION_MODES)}


def validate_execution_context(ctx) -> dict:
    """Mode-specific 校验（第 1 项）：

    SHADOW      account/broker optional；deployment_cap 必须 N/A（None）
    PAPER       paper account + paper broker 必填
    SMALL_LIVE  real account + real broker + deployment_cap 必填
                （CertifiedDecision 在 dispatch 层强制）
    """
    mode = str(getattr(ctx, "execution_mode", "") or "").upper()
    m = validate_execution_mode(mode)
    if not m["valid"]:
        return {"valid": False, "execution_mode": mode,
                "reasons": ["UNKNOWN_EXECUTION_MODE"],
                "rule": "execution_mode 只允许 SHADOW/PAPER/SMALL_LIVE"}
    account = getattr(ctx, "account_id", "") or ""
    broker = getattr(ctx, "broker_name", "") or ""
    cap = getattr(ctx, "deployment_cap", None)
    reasons = []
    if mode == "SHADOW":
        if cap is not None:
            reasons.append("SHADOW_DEPLOYMENT_CAP_NOT_APPLICABLE")
    elif mode == "PAPER":
        if not account:
            reasons.append("PAPER_ACCOUNT_REQUIRED")
        if not broker:
            reasons.append("PAPER_BROKER_REQUIRED")
    elif mode == "SMALL_LIVE":
        if not account:
            reasons.append("REAL_ACCOUNT_REQUIRED")
        if not broker:
            reasons.append("REAL_BROKER_REQUIRED")
        if cap is None:
            reasons.append("DEPLOYMENT_CAP_REQUIRED")
        elif float(cap) < 0.0:
            reasons.append("INVALID_DEPLOYMENT_CAP")
    return {"valid": not reasons, "execution_mode": mode,
            "reasons": reasons,
            "rule": "三种 mode 只改变 Execution 层，不改变 Canonical"}


def canonical_target_of(decision) -> float:
    """统一读取 Canonical FinalTarget（Closure 1）：

        DecisionSnapshot  → decision.target_position
        CertifiedDecision → decision.snapshot["target_position"]

    Paper / Small-Live 一律走本 helper，禁止各模块分别 getattr。"""
    t = getattr(decision, "target_position", None)
    if t is None and hasattr(decision, "snapshot"):
        t = (decision.snapshot or {}).get("target_position")
    try:
        return float(t or 0.0)
    except (TypeError, ValueError):
        return 0.0


def decision_identity_of(decision) -> dict:
    """统一读取 Decision identity（Closure 1）：

        decision_id / release_id / certificate_id / stock_code /
        canonical_action

    兼容 DecisionSnapshot 与 CertifiedDecision 两种承载。"""
    def _get(key, default=""):
        v = getattr(decision, key, None)
        if v is None and hasattr(decision, "snapshot"):
            v = (decision.snapshot or {}).get(key)
        return default if v is None else v
    return {
        "decision_id": _get("decision_id"),
        "release_id": _get("release_id"),
        "certificate_id": _get("certificate_id"),
        "stock_code": _get("stock_code"),
        "canonical_action": _get("canonical_action"),
    }


def assert_mode_not_in_decision_hash(path_hash_input: dict) -> dict:
    """execution_mode 不得出现在 DecisionPathHash 输入中。"""
    present = [k for k in ("execution_mode", "account_id", "broker_name")
               if k in (path_hash_input or {})]
    return {"mode_in_path_hash": bool(present),
            "present_keys": present,
            "violation": bool(present),
            "rule": "execution_mode 是 Operational Context，"
                    "不是 Canonical Decision Input"}


def same_decision_across_modes(evaluate_fn, evidence, release_context,
                               settings, modes=None) -> dict:
    """DoD：同样 Evidence+Release 下 SHADOW/PAPER/SMALL_LIVE →
    完全相同 Canonical Decision（只允许执行层不同）。"""
    modes = modes or list(EXECUTION_MODES)
    results = {}
    hashes = set()
    for mode in modes:
        row = dict(evidence)
        row["release_context"] = dict(release_context)
        snap = evaluate_fn(row, "FLAT", 0.0, settings)
        d = snap.as_dict() if hasattr(snap, "as_dict") else dict(snap)
        results[mode] = {
            "permission": d.get("institutional_permission"),
            "wave": d.get("wave_stage"),
            "fsm_proposal": d.get("fsm_proposal_target"),
            "wave_proposal": d.get("wave_proposal_target"),
            "final_target": d.get("target_position"),
            "canonical_action": d.get("canonical_action"),
            "path_hash": d.get("decision_path_hash"),
        }
        hashes.add(d.get("decision_path_hash"))
    identical = len(hashes) == 1
    return {"results": results,
            "canonical_identical": identical,
            "verdict": "MODE_INVARIANT" if identical
            else "MODE_CHANGED_DECISION"}


def dispatch_runtime(decision_snapshot, execution_context,
                     execution_services=None, conn=None) -> dict:
    """唯一 Runtime Dispatcher（第 1 项）：

        Canonical evaluate ONCE → same DecisionSnapshot
        → dispatch SHADOW / PAPER / SMALL_LIVE

    只允许 ExecutionEvent / DeploymentTarget / ActualPosition 不同；
    Canonical identity（decision_id/path_hash/permission/wave/fsm/
    final_target/action）在任何 mode 下不得被修改。
    """
    mode = str(getattr(execution_context, "execution_mode", "") or "").upper()
    v = validate_execution_context(execution_context)
    if not v["valid"]:
        return {"dispatched": False, "execution_mode": mode,
                "reason": ";".join(v["reasons"]),
                "orders_submitted": False}
    services = execution_services or {}
    if mode == "SHADOW":
        # 永不提交订单：只记录 WOULD_EXECUTE
        identity = decision_identity_of(decision_snapshot)
        event = {
            "event_type": "ORDER_INTENT",
            "event_time": services.get("event_time", ""),
            "decision_id": identity["decision_id"],
            "release_id": identity["release_id"],
            "certificate_id": identity["certificate_id"],
            "execution_mode": "SHADOW",
            "account_id": getattr(execution_context, "account_id", ""),
            "stock_code": identity["stock_code"],
            "side": "WOULD_EXECUTE",
            "payload": {"would_execute": True,
                        "target": canonical_target_of(decision_snapshot)},
        }
        if conn is not None:
            from .runtime_event_ledger import append_runtime_event
            append_runtime_event(conn, event)
        return {"dispatched": True, "execution_mode": "SHADOW",
                "orders_submitted": False,
                "would_execute": True,
                "decision_id": identity["decision_id"]}
    if mode == "PAPER":
        from .execution_gate import assert_execution_eligible
        from .paper_pipeline import paper_order_pipeline
        elig = assert_execution_eligible(decision_snapshot)
        if not elig["eligible"]:
            return {"dispatched": False, "execution_mode": "PAPER",
                    "reason": ";".join(elig["reasons"]),
                    "orders_submitted": False}
        simulator = services.get("simulator")
        current_position = services.get("current_position", 0.0)
        result = paper_order_pipeline(decision_snapshot,
                                      execution_context,
                                      current_position, simulator,
                                      conn=conn)
        return {"dispatched": True, "execution_mode": "PAPER",
                "orders_submitted": result.get("order") is not None,
                "result": result}
    if mode == "SMALL_LIVE":
        from .broker_adapter import (BrokerAdapter,
                                     assert_broker_adapter_contract,
                                     broker_response_event,
                                     normalize_broker_response)
        from .deployment_cap import deployment_target
        from .execution_gate import execute
        from .paper_pipeline import order_intent
        identity = decision_identity_of(decision_snapshot)
        # CertifiedDecision 必须存在（execute 内部强制）
        try:
            cert = execute(decision_snapshot)
        except Exception as exc:
            return {"dispatched": False, "execution_mode": "SMALL_LIVE",
                    "reason": f"CERTIFIED_DECISION_REQUIRED:{exc}",
                    "orders_submitted": False}
        cap = float(getattr(execution_context, "deployment_cap", 0.0) or 0.0)
        canonical_target = canonical_target_of(decision_snapshot)
        dep = deployment_target(
            canonical_target, cap)
        if not dep["valid"]:
            return {"dispatched": False, "execution_mode": "SMALL_LIVE",
                    "reason": dep["reason"], "orders_submitted": False}
        adapter = services.get("broker_adapter")
        if not isinstance(adapter, BrokerAdapter):
            return {"dispatched": False, "execution_mode": "SMALL_LIVE",
                    "reason": "REAL_BROKER_ADAPTER_REQUIRED",
                    "orders_submitted": False}
        contract = assert_broker_adapter_contract(adapter)
        if not contract["contract_ok"]:
            return {"dispatched": False, "execution_mode": "SMALL_LIVE",
                    "reason": "BROKER_CONTRACT_VIOLATION",
                    "orders_submitted": False}
        # Closure 2：Small-Live 必须用与 Paper 相同的 Delta OrderIntent
        # （DeploymentTarget - CurrentPosition），绝不能直接下 DeploymentTarget。
        current_position = float(services.get("current_position", 0.0))
        intent = order_intent(current_position, dep["deployment_target"])
        order = {
            "side": intent["side"],
            "quantity": intent["quantity"],
            "canonical_target": dep["canonical_target"],
            "deployment_target": dep["deployment_target"],
            "current_position": current_position,
            "delta": intent["delta"],
        }
        if intent["side"] == "NONE":
            return {"dispatched": True, "execution_mode": "SMALL_LIVE",
                    "orders_submitted": False,
                    "reason": "NO_DELTA_NO_ORDER",
                    "deployment": dep, "intent": intent,
                    "certificate": cert}
        raw = adapter.submit_order(order)
        normalized = normalize_broker_response(
            raw, getattr(adapter, "name", "BROKER_REAL"),
            request_id=f"REQ-{order['quantity']}")
        if conn is not None:
            # Closure 3：Broker Event 必须带 decision/release/certificate
            # 身份；落库失败 → EXECUTION_UNVERIFIED / NO_NEW_RISK，
            # 不能返回 dispatched=True。
            ev = broker_response_event(
                conn, normalized,
                decision_id=identity["decision_id"],
                release_id=identity["release_id"],
                certificate_id=identity["certificate_id"],
                execution_mode="SMALL_LIVE",
                event_time=services.get("event_time", ""))
            if not ev.get("inserted"):
                return {"dispatched": False,
                        "execution_mode": "SMALL_LIVE",
                        "orders_submitted": False,
                        "reason": "BROKER_RESPONSE_UNPERSISTED:NO_NEW_RISK",
                        "event": ev,
                        "deployment": dep}
        return {"dispatched": True, "execution_mode": "SMALL_LIVE",
                "orders_submitted": True,
                "deployment": dep,
                "intent": intent,
                "order": order,
                "broker_response": normalized,
                "certificate": cert}
    return {"dispatched": False, "execution_mode": mode,
            "reason": "UNKNOWN_EXECUTION_MODE",
            "orders_submitted": False}
