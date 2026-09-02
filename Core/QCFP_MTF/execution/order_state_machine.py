# coding: utf-8
"""Order State Machine + Position Reconciliation（Release 2：新 16 号）

最小订单状态：INTENT → SENT → ACKNOWLEDGED → PARTIAL/FILLED
             或 REJECTED / CANCELLED / UNKNOWN

UNKNOWN（如 network timeout）→ 禁止重发/新订单 → 查询 broker → reconcile。
Position Truth：CanonicalTarget vs InternalPosition vs BrokerPosition →
IN_SYNC / PARTIAL / MISMATCH / UNKNOWN；MISMATCH/UNKNOWN → NO_NEW_RISK。
"""


ORDER_STATES = ("INTENT", "SENT", "ACKNOWLEDGED", "PARTIAL", "FILLED",
                "REJECTED", "CANCELLED", "UNKNOWN")


class OrderStateMachine:
    def __init__(self):
        self.orders = {}

    def send(self, order_id, size) -> dict:
        if order_id in self.orders:
            return {"state": "DUPLICATE_BLOCKED",
                    "reason": "重复下单被阻止（必须先 reconcile）"}
        self.orders[order_id] = {"state": "SENT", "size": size}
        return {"state": "SENT", "size": size}

    def ack(self, order_id, fill=None) -> dict:
        if order_id not in self.orders:
            return {"state": "UNKNOWN", "reason": "订单不存在"}
        if self.orders[order_id]["state"] == "UNKNOWN":
            return {"state": "UNKNOWN",
                    "reason": "UNKNOWN 状态下必须先查询 broker 再 reconcile"}
        if fill is None:
            self.orders[order_id]["state"] = "ACKNOWLEDGED"
        elif float(fill) <= 0:
            self.orders[order_id]["state"] = "REJECTED"
        elif float(fill) < float(self.orders[order_id]["size"]):
            self.orders[order_id]["state"] = "PARTIAL"
        else:
            self.orders[order_id]["state"] = "FILLED"
        return {"state": self.orders[order_id]["state"]}

    def reject(self, order_id, reason="") -> dict:
        """显式 REJECT（Runtime Evidence Wiring：第 5 项）。
        不再用 ack(fill=0) 隐式表达 Reject。"""
        if order_id not in self.orders:
            return {"state": "UNKNOWN", "reason": "订单不存在"}
        self.orders[order_id]["state"] = "REJECTED"
        self.orders[order_id]["reject_reason"] = reason
        return {"state": "REJECTED", "reason": reason or "REJECTED"}

    def timeout(self, order_id) -> dict:
        """network timeout → UNKNOWN → 禁止重发/新订单。"""
        self.orders[order_id]["state"] = "UNKNOWN"
        return {"state": "UNKNOWN",
                "block_new_order": True,
                "action": "QUERY_BROKER_AND_RECONCILE"}

    def cancel(self, order_id) -> dict:
        self.orders[order_id]["state"] = "CANCELLED"
        return {"state": "CANCELLED"}


def position_reconciliation(canonical_target, internal_position,
                            broker_position=None) -> dict:
    """Position Truth：CanonicalTarget vs Internal vs Broker。"""
    canonical = float(canonical_target or 0.0)
    internal = float(internal_position or 0.0)
    if broker_position is None:
        return {"status": "UNKNOWN",
                "no_new_risk": True,
                "reason": "Broker position 未知 → UNKNOWN → NO_NEW_RISK"}
    broker = float(broker_position)
    if abs(internal - broker) > 1e-6:
        return {"status": "MISMATCH",
                "no_new_risk": True,
                "reason": "Internal vs Broker 不一致 → NO_NEW_RISK"}
    if abs(canonical - broker) > 1e-6:
        return {"status": "PARTIAL",
                "no_new_risk": abs(canonical - broker) > 0.05,
                "reason": "与 Canonical 目标存在差异（同步中）"}
    return {"status": "IN_SYNC", "no_new_risk": False,
            "reason": "Canonical/Internal/Broker 一致"}
