# coding: utf-8
"""Risk Budget Utilization Audit（QCFP-MTF 2.8：66 号风险预算利用率审计）

统计 available / requested / approved / executed / unused risk。
避免系统"有仓位上限，但长期根本不知道用了多少风险"。

验收标准：不要只报告"持仓 35%"，而要知道这是
风险预算的主动选择还是约束结果。
"""


def risk_budget_utilization(budget: dict) -> dict:
    """budget：{available, requested, approved, executed}。"""
    available = float(budget.get("available") or 0.0)
    requested = float(budget.get("requested") or 0.0)
    approved = float(budget.get("approved") or 0.0)
    executed = float(budget.get("executed") or 0.0)
    unused = round(max(0.0, available - executed), 4)
    utilization = round(executed / available, 4) if available else None
    if utilization is None:
        band = "NO_BUDGET"
    elif utilization < 0.30:
        band = "LOW"
    elif utilization >= 0.90:
        band = "HIGH"
    else:
        band = "MODERATE"
    return {
        "available": round(available, 4),
        "requested": round(requested, 4),
        "approved": round(approved, 4),
        "executed": round(executed, 4),
        "unused": unused,
        "utilization": utilization,
        "band": band,
        "approved_vs_requested": round(approved / requested, 4)
        if requested else None,
    }


def utilization_diagnosis(audit: dict) -> dict:
    """低利用率 → 排查 Permission/Wave/Portfolio/市场；高 → 集中风险。"""
    band = audit.get("band")
    if band == "LOW":
        return {"verdict": "UNUSED_BUDGET",
                "guidance": "风险预算长期只用了 <30%：排查 Permission "
                            "过严 / Wave 太少 / Portfolio cap 过严 / "
                            "市场本无机会"}
    if band == "HIGH":
        return {"verdict": "CONCENTRATION_RISK",
                "guidance": "风险预算长期 90%+：关注集中风险与尾部暴露"}
    return {"verdict": "MODERATE",
            "guidance": "利用率适中，属主动选择或正常约束结果"}


def risk_efficiency_report(budget: dict) -> dict:
    """新 66 号：正式 Portfolio/Production 报告同时展示
    Available / Approved / Executed / Unused Risk，而不是只有仓位百分比。"""
    audit = risk_budget_utilization(budget)
    diagnosis = utilization_diagnosis(audit)
    return {
        "available_risk": audit["available"],
        "approved_risk": audit["approved"],
        "executed_risk": audit["executed"],
        "unused_risk": audit["unused"],
        "utilization": audit["utilization"],
        "band": audit["band"],
        "diagnosis": diagnosis,
        "report_rule": "正式报告必须展示 Available/Approved/Executed/"
                       "Unused Risk，而不是只有仓位百分比",
    }


def risk_budget_lineage(budget: dict,
                        broker_actual_risk=None) -> dict:
    """Release 3（新 26 号）：Available→Requested→Approved→Canonical
    Target→Executed→Broker Actual 完整链路，回答
    "35% 是主动选择还是被压下来的"。"""
    available = float(budget.get("available") or 0.0)
    requested = float(budget.get("requested") or 0.0)
    approved = float(budget.get("approved") or 0.0)
    executed = float(budget.get("executed") or 0.0)
    constrained = requested > approved + 1e-9
    return {
        "available": round(available, 4),
        "requested": round(requested, 4),
        "approved": round(approved, 4),
        "executed": round(executed, 4),
        "broker_actual": broker_actual_risk,
        "constrained_down": constrained,
        "explanation": ("Proposal 被 Liquidity/Portfolio 压下来"
                        if constrained else "系统主动选择只用这么多"),
        "rule": "35% 要能回答是主动选择还是约束结果",
    }
