# coding: utf-8
"""Failure Mode / Safe Degradation（QCFP-MTF 2.8：39 号自动降级机制）

"系统不知道时，必须知道自己不知道"：
    正常 → DEGRADED → OBSERVE → HALTED

各类失败对应动作：
    Data DEGRADED    → Permission 自动收紧（禁新增）
    PIT FAIL         → BLOCK（禁止交易）
    Feature Failure  → BLOCK
    Model Failure    → DEGRADED（降仓观察）
    Ledger 写入失败   → 不允许 Trade
    Replay mismatch  → HALTED

核心原则：任何关键事实无法证明，就不能继续提高风险。
"""


FAILURE_ACTIONS = {
    "data_failure": {"status": "DEGRADED", "action": "PERMISSION_TIGHTEN",
                     "block_new_risk": True},
    "pit_failure": {"status": "BLOCK", "action": "NO_TRADE",
                    "block_new_risk": True},
    "feature_failure": {"status": "BLOCK", "action": "NO_TRADE",
                        "block_new_risk": True},
    "model_failure": {"status": "DEGRADED", "action": "REDUCE_OBSERVE",
                      "block_new_risk": True},
    "permission_failure": {"status": "OBSERVE", "action": "NO_NEW_RISK",
                           "block_new_risk": True},
    "wave_failure": {"status": "OBSERVE", "action": "WAIT_CONFIRM",
                     "block_new_risk": True},
    "risk_failure": {"status": "DEGRADED", "action": "REDUCE",
                     "block_new_risk": True},
    "portfolio_failure": {"status": "DEGRADED", "action": "REDUCE",
                          "block_new_risk": True},
    "execution_failure": {"status": "OBSERVE", "action": "HOLD",
                          "block_new_risk": True},
    "ledger_failure": {"status": "BLOCK", "action": "NO_TRADE",
                       "block_new_risk": True},
    "replay_failure": {"status": "HALTED", "action": "HALT",
                       "block_new_risk": True},
}

SEVERITY = {"正常": 0, "DEGRADED": 1, "OBSERVE": 2, "BLOCK": 3, "HALTED": 4}


def failure_degradation(failures: dict) -> dict:
    """failures：{failure_name: True/False} → 降级状态 + 动作。"""
    triggered = [k for k, v in (failures or {}).items() if v]
    actions = []
    worst = "正常"
    for name in triggered:
        spec = FAILURE_ACTIONS.get(name, {"status": "DEGRADED",
                                          "action": "REVIEW",
                                          "block_new_risk": True})
        actions.append({"failure": name, "status": spec["status"],
                        "action": spec["action"],
                        "block_new_risk": spec["block_new_risk"]})
        if SEVERITY[spec["status"]] > SEVERITY[worst]:
            worst = spec["status"]
    return {"status": worst, "triggered": triggered, "actions": actions,
            "block_new_risk": worst in ("BLOCK", "HALTED")
            or any(a["block_new_risk"] for a in actions)}


def apply_degradation(target, previous_position, failures) -> dict:
    """把降级状态作用到目标仓位：
        BLOCK/HALTED → 0（禁止）
        DEGRADED/OBSERVE → 不新增（target ≤ previous）
    """
    d = failure_degradation(failures)
    t = float(target or 0.0)
    prev = float(previous_position or 0.0)
    if d["status"] in ("BLOCK", "HALTED"):
        t = 0.0
    elif d["block_new_risk"] and t > prev + 1e-9:
        t = min(t, prev)
    return {"target": round(t, 4), "degradation": d}
