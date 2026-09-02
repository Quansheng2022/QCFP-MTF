# coding: utf-8
"""Broker Adapter（Runtime Evidence Wiring：第 8 项）

状态：OPTIONAL_EXECUTION_EXTENSION（P1-7 目标重新对齐）
QCFP_MTF 是辅助决策支持系统，不负责向 Broker 下交易指令。
本模块保留为可选执行扩展，不参与 Decision Support Qualification；
Broker 缺失不会导致 Decision Support Release NOT_PROVEN。

Broker Adapter 只允许 5 件事：
    submit_order / query_order / query_fills / query_positions / cancel_order
绝不允许计算 target、改变 permission/action/risk。

UNKNOWN 是必须保留的事实：network timeout 不能写成 FAILED 或 FILLED，
只能 UNKNOWN → No New Order → Query Broker → Reconcile。

Runtime Evidence Wiring 修改：
    * Contract Validation 不再只看方法名存在——必须验证 subclass 真正
      override；未 override → NOT_IMPLEMENTED → contract fail；
    * 统一 Broker Response Schema（raw_status/normalized_status/
      fill/position 字段）；
    * 任何 Broker Response 先落 Runtime Event（broker_response_event），
      再 OSM 转换 → 仓位更新 → Reconciliation（event-first）；
    * UNKNOWN Resolution：query → fills → positions → reconciliation，
      只有 Resolved 才允许恢复新风险。
"""


BROKER_METHODS = ("submit_order", "query_order", "query_fills",
                  "query_positions", "cancel_order")


class BrokerAdapter:
    """最小 Broker 接口（Paper Proxy / Small-Live Real 共用）。"""

    def __init__(self, name="PAPER_PROXY"):
        self.name = name

    def submit_order(self, order_intent) -> dict:
        raise NotImplementedError

    def query_order(self, broker_order_id) -> dict:
        raise NotImplementedError

    def query_fills(self, broker_order_id) -> dict:
        raise NotImplementedError

    def query_positions(self, account_id, stock_code=None) -> dict:
        raise NotImplementedError

    def cancel_order(self, broker_order_id) -> dict:
        raise NotImplementedError


def assert_broker_adapter_contract(adapter: BrokerAdapter) -> dict:
    """Adapter 必须真正 override 5 个方法；不允许决策计算。

    仅靠方法名存在不够：必须验证
        type(adapter).submit_order is not BrokerAdapter.submit_order
    否则视为 NOT_IMPLEMENTED（Contract Ready ≠ Broker Reality Ready）。"""
    forbidden = ("calculate_target", "change_permission", "change_action",
                 "change_risk", "evaluate")
    methods = [m for m in dir(adapter)
               if callable(getattr(adapter, m, None))
               and not m.startswith("_")]
    extra = [m for m in methods if m not in BROKER_METHODS
             and m not in forbidden]
    not_implemented = []
    for m in BROKER_METHODS:
        impl = getattr(type(adapter), m, None)
        base = getattr(BrokerAdapter, m, None)
        if impl is base or impl is None:
            not_implemented.append(m)
    return {"broker_methods": [m for m in BROKER_METHODS
                               if hasattr(adapter, m)],
            "forbidden_methods_present": [m for m in forbidden
                                          if hasattr(adapter, m)],
            "extra_methods": extra,
            "not_implemented": not_implemented,
            "contract_ok": not extra
            and not any(hasattr(adapter, m) for m in forbidden)
            and not not_implemented,
            "rule": "Subclass 必须真正 override 全部 5 个方法；"
                    "未实现 → NOT_IMPLEMENTED，不能 contract_ok=True"}


def broker_timeout_result(broker_order_id) -> dict:
    """network timeout → UNKNOWN（不得写成 FAILED/FILLED）。"""
    return {"broker_order_id": broker_order_id,
            "status": "UNKNOWN",
            "block_new_order": True,
            "action": "QUERY_BROKER_AND_RECONCILE",
            "rule": "UNKNOWN 是必须保留的事实，不能自动当 REJECT/FILL"}


def normalize_broker_response(raw: dict, broker: str,
                              request_id="") -> dict:
    """统一 Broker Response Schema（第 8 项第二层）。

    Order/ACK：broker/broker_order_id/raw_status/normalized_status/
    observed_at/source_timestamp/request_id
    Fill：fill_id/quantity/price/commission/stamp_duty/exchange_fee/
    other_fee
    Position：account_id/stock_code/quantity/market_value/observed_at
    """
    raw = raw or {}
    normalized_status = str(raw.get("status") or
                            raw.get("raw_status") or "UNKNOWN").upper()
    known = ("ACK", "FILLED", "PARTIAL", "REJECTED", "CANCELLED",
             "UNKNOWN")
    if normalized_status not in known:
        normalized_status = "UNKNOWN"
    base = {
        "broker": broker,
        "broker_order_id": raw.get("broker_order_id") or "",
        "raw_status": str(raw.get("status") or raw.get("raw_status")
                          or ""),
        "normalized_status": normalized_status,
        "observed_at": raw.get("observed_at") or "",
        "source_timestamp": raw.get("source_timestamp") or "",
        "request_id": request_id,
    }
    if "fill" in raw or "fills" in raw:
        fills = raw.get("fills") or ([raw["fill"]] if "fill" in raw
                                     else [])
        first = fills[0] if fills else {}
        base.update({
            "fill_id": first.get("fill_id") or "",
            "quantity": first.get("quantity"),
            "price": first.get("price"),
            "commission": first.get("commission"),
            "stamp_duty": first.get("stamp_duty"),
            "exchange_fee": first.get("exchange_fee"),
            "other_fee": first.get("other_fee"),
        })
    if raw.get("position") is not None or raw.get("positions") is not None:
        pos = raw.get("position") or (raw.get("positions") or [{}])[0]
        base.update({
            "account_id": pos.get("account_id") or "",
            "stock_code": pos.get("stock_code") or "",
            "quantity": pos.get("quantity"),
            "market_value": pos.get("market_value"),
            "observed_at": pos.get("observed_at") or base["observed_at"],
        })
    return base


def broker_response_event(conn, normalized: dict,
                          decision_id="", release_id="",
                          execution_mode="SMALL_LIVE",
                          certificate_id="", event_time="") -> dict:
    """Event-first（第 8 项第三层）：任何 Broker Response 先落
    Runtime Event，再允许 OSM 转换/仓位更新/Reconciliation。"""
    from .runtime_event_ledger import append_runtime_event
    status = normalized.get("normalized_status") or "UNKNOWN"
    event_type = {
        "ACK": "ORDER_ACK", "FILLED": "FILL", "PARTIAL": "PARTIAL_FILL",
        "REJECTED": "ORDER_REJECT", "CANCELLED": "ORDER_CANCEL",
    }.get(status, "ORDER_UNKNOWN")
    event = {
        "event_id": f"BR-{normalized.get('broker_order_id') or '?'}-"
                    f"{normalized.get('request_id') or '?'}",
        "event_type": event_type,
        "event_time": event_time or normalized.get("observed_at") or "",
        "decision_id": decision_id,
        "release_id": release_id,
        "certificate_id": certificate_id,
        "execution_mode": execution_mode,
        "account_id": normalized.get("account_id") or "",
        "stock_code": normalized.get("stock_code") or "",
        "broker_order_id": normalized.get("broker_order_id") or "",
        "filled_qty": normalized.get("quantity"),
        "fill_price": normalized.get("price"),
        "commission": normalized.get("commission"),
        "stamp_duty": normalized.get("stamp_duty"),
        "exchange_fee": normalized.get("exchange_fee"),
        "other_fee": normalized.get("other_fee"),
        "broker_position": normalized.get("quantity"),
        "reconciliation_status": "IN_SYNC"
        if status in ("FILLED", "ACK") else
        "MISMATCH" if status == "PARTIAL" else "UNKNOWN",
        "payload": {"normalized": normalized},
    }
    return append_runtime_event(conn, event)


def resolve_broker_unknown(conn, broker_order_id, release_id,
                           queries=None, decision_id="",
                           certificate_id="") -> dict:
    """UNKNOWN Resolution（第 8 项第四层）：
        query_order → query_fills → query_positions → RECONCILIATION
    只有 Resolved 才允许恢复新风险；仍 UNKNOWN → 继续禁止。"""
    from .order_state_machine import position_reconciliation
    from .runtime_event_ledger import append_runtime_event
    queries = queries or {}
    order = queries.get("query_order") or {}
    fills = queries.get("query_fills") or []
    positions = queries.get("query_positions") or {}
    order_status = str(order.get("status") or "").upper()
    if order_status in ("FILLED", "PARTIAL", "REJECTED", "CANCELLED"):
        normalized = normalize_broker_response(
            {"status": order_status, "broker_order_id": broker_order_id,
             "fills": fills, "position": positions},
            broker=queries.get("broker", "BROKER_REAL"),
            request_id=f"RESOLVE-{broker_order_id}")
        ev = broker_response_event(conn, normalized,
                                   decision_id=decision_id,
                                   release_id=release_id,
                                   certificate_id=certificate_id)
        # Event-first：事件未落库 → 不得视为 Resolved（fail-closed）
        resolved = bool(ev.get("inserted"))
        status = order_status
    else:
        broker_pos = positions.get("quantity")
        recon = position_reconciliation(
            queries.get("canonical_target", 0.0),
            queries.get("internal_position", 0.0),
            broker_pos)
        ev = append_runtime_event(conn, {
            "event_id": f"RC-UNK-{broker_order_id}",
            "event_type": "RECONCILIATION",
            "event_time": "",
            "decision_id": decision_id,
            "release_id": release_id,
            "execution_mode": "SMALL_LIVE",
            "stock_code": positions.get("stock_code") or "",
            "broker_order_id": broker_order_id,
            "internal_position": queries.get("internal_position"),
            "broker_position": broker_pos,
            "reconciliation_status": recon["status"],
            "payload": {"reconciliation": recon}})
        resolved = recon["status"] == "IN_SYNC" and bool(ev.get("inserted"))
        status = recon["status"]
    return {"broker_order_id": broker_order_id,
            "resolved": resolved,
            "status": status,
            "new_risk_allowed": resolved,
            "action": "RECONCILE_AND_CONTINUE" if resolved
            else "STAY_BLOCKED_QUERY_AGAIN",
            "rule": "只有 Resolved 才允许恢复新风险"}
