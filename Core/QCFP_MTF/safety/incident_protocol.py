# coding: utf-8
"""Production Incident / Decision Halt Protocol（QCFP-MTF 2.8：39 号）

清晰 incident 状态机：
    NORMAL → DEGRADED → SAFE_MODE → DECISION_HALTED →
    RECOVERY_VALIDATION → NORMAL

区分 SYSTEM_FAILURE（Ledger/Replay 损坏 → 停止未验证新指令）
与 MARKET_RISK_HARD_EXIT（模型判断清仓）。
恢复后必须 Replay 验证，不能简单 restart 即恢复 Production。
"""


INCIDENT_STATES = ("NORMAL", "DEGRADED", "SAFE_MODE", "DECISION_HALTED",
                   "RECOVERY_VALIDATION")


def incident_protocol(failure_kind="", replay_verified=False) -> dict:
    """incident 状态机推进。

    failure_kind：SYSTEM_FAILURE（Ledger/Replay/PIT 损坏）
                  MARKET_RISK_HARD_EXIT（风险事件）
    """
    if failure_kind == "SYSTEM_FAILURE":
        # 系统不可信 → 停止新指令（不是自动清仓）
        return {
            "state": "DECISION_HALTED",
            "halt_new_decisions": True,
            "force_exit": False,
            "reason": "SYSTEM_FAILURE：停止未经验证的新交易指令",
            "recovery_required": True,
        }
    if failure_kind == "MARKET_RISK_HARD_EXIT":
        return {
            "state": "SAFE_MODE",
            "halt_new_decisions": True,
            "force_exit": True,
            "reason": "MARKET_RISK_HARD_EXIT：风险事件要求退出",
            "recovery_required": False,
        }
    if failure_kind == "DEGRADED":
        return {"state": "DEGRADED", "halt_new_decisions": False,
                "force_exit": False, "reason": "DEGRADED",
                "recovery_required": False}
    if failure_kind == "RECOVERY_VALIDATION":
        return {
            "state": "RECOVERY_VALIDATION",
            "halt_new_decisions": True,
            "force_exit": False,
            "reason": "恢复前必须 Replay 验证",
            "recovery_required": True,
            "replay_verified": bool(replay_verified),
        }
    return {"state": "NORMAL", "halt_new_decisions": False,
            "force_exit": False, "reason": "NORMAL",
            "recovery_required": False}


def recover_production(incident: dict, replay_verified=False) -> dict:
    """恢复：必须 Replay 验证通过才能回到 NORMAL（不能简单 restart）。"""
    if incident.get("state") not in ("DECISION_HALTED", "RECOVERY_VALIDATION"):
        return {"recovered": True, "state": incident.get("state", "NORMAL"),
                "note": "无需恢复"}
    if not replay_verified:
        return {"recovered": False,
                "state": "RECOVERY_VALIDATION",
                "note": "必须 Replay 验证通过才能恢复 Production"}
    return {"recovered": True, "state": "NORMAL",
            "note": "Replay 验证通过，恢复 Production"}


def incident_policy_table() -> dict:
    """新 39 号：每种 Incident 必须定义
    new decision / new order / risk reduction / forced liquidation /
    replay required / human approval required。"""
    base = {
        "new_decision_allowed": False,
        "new_order_allowed": False,
        "risk_reduction_allowed": True,
        "forced_liquidation": False,
        "replay_required": True,
        "human_approval_required": True,
    }
    return {
        "NORMAL": {
            "new_decision_allowed": True,
            "new_order_allowed": True,
            "risk_reduction_allowed": True,
            "forced_liquidation": False,
            "replay_required": False,
            "human_approval_required": False,
        },
        "DEGRADED": dict(base, new_decision_allowed=True,
                         replay_required=False),
        "SAFE_MODE": dict(base, risk_reduction_allowed=True,
                          forced_liquidation=False),
        "DECISION_HALTED_SYSTEM_FAILURE": dict(
            base, forced_liquidation=False,
            reason="SYSTEM_FAILURE：停新指令≠清仓"),
        "DECISION_HALTED_MARKET_RISK": dict(
            base, forced_liquidation=True,
            replay_required=False,
            reason="MARKET_RISK_HARD_EXIT：风险事件要求退出"),
        "RECOVERY_VALIDATION": dict(base),
        "rule": "系统自己不可信时，不能因为'安全'就自动清仓；"
                "SYSTEM FAILURE ≠ MARKET RISK",
    }
