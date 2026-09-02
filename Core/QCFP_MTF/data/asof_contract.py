# coding: utf-8
"""AsOfTimeContract（QCFP-MTF 2.8：33 号统一时间语义）

统一五类时间：
    observation_time / available_time / decision_time /
    execution_time / outcome_time

每个 Evidence 字段必须回答：
    数据什么时候产生（observation）/
    什么时候被市场知道（available）/
    什么时候首次允许进入决策（decision ≤ available）。
"""


TIME_ROLES = ("observation_time", "period_end", "source_publish_time",
              "system_available_time", "available_time", "decision_time",
              "execution_time", "outcome_time")


def asof_time_contract(evidence: dict, decision_time: str) -> dict:
    """校验时间语义：
        available_time ≤ decision_time（PIT）
        decision_time ≤ execution_time ≤ outcome_time（因果序）
    """
    violations = []
    available = evidence.get("available_time") or \
        evidence.get("available_at")
    if available and str(available)[:10] > str(decision_time)[:10]:
        violations.append(f"PIT: available={available} > "
                          f"decision={decision_time}")
    exec_t = evidence.get("execution_time")
    if exec_t and str(decision_time)[:10] > str(exec_t)[:10]:
        violations.append(f"因果序: decision={decision_time} > "
                          f"execution={exec_t}")
    outcome = evidence.get("outcome_time")
    if exec_t and outcome and str(exec_t)[:10] > str(outcome)[:10]:
        violations.append(f"因果序: execution={exec_t} > "
                          f"outcome={outcome}")
    return {
        "time_roles": {r: evidence.get(r, "") for r in TIME_ROLES},
        "decision_time": str(decision_time)[:10],
        "violations": violations,
        "pit_valid": not violations,
    }


def assert_asof_time_valid(evidence: dict, decision_time: str) -> None:
    r = asof_time_contract(evidence, decision_time)
    if not r["pit_valid"]:
        from ..governance.feature_gate import FeatureGateError
        raise FeatureGateError("; ".join(r["violations"]))


def evidence_time_completeness(evidence: dict) -> dict:
    """新 21 号：Production Evidence 不能只带一个 date。

    至少必须带 as_of_time / available_time / decision_time，
    并保证 available_time <= decision_time。
    """
    as_of = evidence.get("as_of_time") or evidence.get(
        "observation_time") or evidence.get("period_end")
    available = evidence.get("available_time") or \
        evidence.get("system_available_time")
    decision = evidence.get("decision_time")
    missing = []
    if not as_of:
        missing.append("as_of_time")
    if not available:
        missing.append("available_time")
    if not decision:
        missing.append("decision_time")
    order_ok = True
    if available and decision:
        order_ok = str(available)[:10] <= str(decision)[:10]
    return {
        "as_of_time": as_of,
        "available_time": available,
        "decision_time": decision,
        "missing": missing,
        "complete": not missing,
        "available_before_decision": order_ok,
        "valid": not missing and order_ok,
        "rule": "PIT 不只是日期没穿越，而是市场当时真的已经知道",
    }


MARKET_SESSIONS = ("before_open", "continuous_session", "lunch_break",
                   "after_close", "auction", "suspension", "half_day")


def trading_session_contract(available_time, decision_time,
                             session="after_close") -> dict:
    """新 33 号：把 available/decision/execution 映射到正式交易时段。

    如果财报 16:45 发布（after_close），当天收盘价不能作为发布后
    可执行价格——可执行时间必须至少是 next tradable session。
    """
    if session not in MARKET_SESSIONS:
        return {"valid": False, "reason": f"未知交易时段 {session}"}
    next_session = session in ("after_close", "auction", "half_day")
    execution_time = decision_time if not next_session else None
    return {
        "available_time": str(available_time or "")[:10],
        "decision_time": str(decision_time or "")[:10],
        "session": session,
        "next_tradable_session_required": next_session,
        "execution_time": execution_time,
        "valid": True,
        "rule": "发布晚于收盘 → 当天收盘价不可执行，"
                "至少 next tradable session",
    }


def execution_time_resolution(available_time, decision_time,
                              execution_time, session) -> dict:
    """新 33 号：同一 Evidence 的 Backtest/Replay/Execution 可执行时间一致。"""
    contract = trading_session_contract(available_time, decision_time,
                                        session)
    if contract["next_tradable_session_required"] \
            and str(execution_time or "")[:10] <= str(decision_time)[:10]:
        return {"consistent": False,
                "reason": "发布后须 next tradable session 才可执行",
                "contract": contract}
    return {"consistent": True, "contract": contract}
