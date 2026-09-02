# coding: utf-8
"""Safety Kill-Switch（QCFP-MTF 2.7：系统级最后安全防线）

状态：NORMAL → WARNING → SAFE_MODE → HALTED
    SAFE_MODE：禁止新增风险（允许既有仓位风险管理）
    HALTED：禁止所有新决策
Kill Switch 不可被 Wave / Permission / Strategy Override。
"""

CHECK_TO_STATUS = {
    "data_failure": "SAFE_MODE",
    "pit_failure": "SAFE_MODE",
    "model_drift": "SAFE_MODE",
    "execution_failure": "SAFE_MODE",
    "governance_failure": "SAFE_MODE",      # 2.8（30 号）：治理违规 → SAFE_MODE
    "unknown_production_evidence": "SAFE_MODE",  # 关键监控指标缺失 → SAFE_MODE
    "risk_breach": "WARNING",
    "abnormal_market": "WARNING",
    "permission_drift": "WARNING",           # 2.8（30 号）
    "wave_perf_degraded": "WARNING",
    "liquidity_low": "WARNING",
    "mfe_mae_biased": "WARNING",
    "false_entry_high": "WARNING",
    "ledger_failure": "HALTED",
    "replay_failure": "HALTED",
}


def evaluate_safety(checks: dict) -> dict:
    """checks: {name: bool(triggered)} → {status, triggered}"""
    triggered = [k for k, v in (checks or {}).items() if v]
    status = "NORMAL"
    for k in triggered:
        s = CHECK_TO_STATUS.get(k, "WARNING")
        if s == "HALTED":
            status = "HALTED"
        elif s == "SAFE_MODE" and status != "HALTED":
            status = "SAFE_MODE"
        elif s == "WARNING" and status == "NORMAL":
            status = "WARNING"
    return {"status": status, "triggered": triggered}


def safety_gate(checks: dict, target, previous_position=0.0) -> dict:
    """安全门：SAFE_MODE 禁新增风险；HALTED 全部归零"""
    st = evaluate_safety(checks)
    t = float(target or 0.0)
    prev = float(previous_position or 0.0)
    blocked = None
    if st["status"] == "HALTED":
        t, blocked = 0.0, "HALTED"
    elif st["status"] == "SAFE_MODE" and t > prev + 1e-9:
        t, blocked = 0.0, "SAFE_MODE_NEW_RISK_BLOCKED"
    return {"status": st["status"], "target": round(t, 4),
            "blocked_reason": blocked, "triggered": st["triggered"]}
