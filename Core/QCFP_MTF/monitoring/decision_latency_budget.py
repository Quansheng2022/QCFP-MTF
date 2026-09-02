# coding: utf-8
"""Decision Latency Budget（QCFP-MTF 2.8：68 号决策延迟预算）

防止研究越来越复杂导致信号失去时效性。只记录关键阶段：
    Data ready → Evidence ready → Canonical Decision → Ledger committed
    → Executable instruction

验收标准：每个 Production release 的计算耗时不能无解释持续增长；
复杂度增加若没有实战增量价值却显著增加 latency → 优先回退。
"""


LATENCY_STAGES = ("data_ready", "evidence_ready", "canonical_decision",
                  "ledger_committed", "executable_instruction")


def decision_latency_budget(latencies_ms: dict) -> dict:
    """latencies_ms：各阶段耗时（毫秒，累计或单段均可，统一按单段）。"""
    stages = {s: float(latencies_ms.get(s) or 0.0)
              for s in LATENCY_STAGES}
    total = round(sum(stages.values()), 1)
    return {"stages": stages, "total_ms": total,
            "note": "牛散日/周级波段不需要低延迟，"
                    "但计算耗时不能无解释持续增长"}


def latency_budget_check(total_ms: float, budget_ms: float) -> dict:
    return {"total_ms": round(float(total_ms), 1),
            "budget_ms": round(float(budget_ms), 1),
            "within_budget": float(total_ms) <= float(budget_ms)}


def latency_regression_check(previous_total_ms, current_total_ms,
                             max_growth: float = 0.20) -> dict:
    """当前耗时相对上一版增长超 max_growth → 回退建议。"""
    prev = float(previous_total_ms or 0.0)
    cur = float(current_total_ms or 0.0)
    growth = round((cur - prev) / prev, 4) if prev else None
    if growth is not None and growth > max_growth:
        return {"verdict": "ROLLBACK_ADVICE",
                "growth": growth,
                "guidance": "延迟无解释增长，且无实战增量价值 → 优先回退"}
    return {"verdict": "ACCEPTABLE",
            "growth": growth,
            "guidance": "延迟增长在预算内或可解释"}


def latency_value_justification(latency_report: dict,
                                complexity_delta: float = 0.0,
                                oos_incremental_value: float = 0.0) -> dict:
    """新 68 号：Latency 明显增加的 Release 必须同时证明
    Incremental Practical Value，否则优先回退复杂度。"""
    verdict = latency_report.get("verdict")
    growth = latency_report.get("growth")
    if verdict == "ROLLBACK_ADVICE" and \
            oos_incremental_value <= 0.01:
        return {"decision": "ROLLBACK_COMPLEXITY",
                "reason": "延迟显著增加但 OOS 增量价值 <1% → 回退复杂度",
                "complexity_delta": complexity_delta,
                "oos_incremental_value": oos_incremental_value,
                "rollback": True}
    if verdict == "ROLLBACK_ADVICE" and oos_incremental_value >= 0.01:
        return {"decision": "KEEP_WITH_EVIDENCE",
                "reason": "延迟增加但已证明 Incremental Practical Value",
                "complexity_delta": complexity_delta,
                "oos_incremental_value": oos_incremental_value,
                "rollback": False}
    return {"decision": "ACCEPTABLE",
            "reason": "延迟增长在预算内",
            "complexity_delta": complexity_delta,
            "oos_incremental_value": oos_incremental_value,
            "rollback": False}
