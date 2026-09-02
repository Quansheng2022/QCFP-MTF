# coding: utf-8
"""Module Retirement / Sunset Governance（QCFP-MTF 2.8：40 号模块退役治理）

成熟系统必须有退休机制（RETIRE 是正常状态，不是失败）：
    PROPOSED → EXPERIMENTAL → CANDIDATE → SHADOW → CERTIFIED →
    PRODUCTION → DEGRADED → REVIEW → RETIRED

退休条件：Incremental Alpha ≈ 0 + Complexity ↑ + Data Risk ↑
"""


MODULE_LIFECYCLE = ("PROPOSED", "EXPERIMENTAL", "CANDIDATE", "SHADOW",
                    "CERTIFIED", "PRODUCTION", "DEGRADED", "REVIEW",
                    "RETIRED")


def module_retirement_decision(module, incremental_alpha,
                               complexity_delta, data_risk) -> dict:
    """模块退役判定。"""
    alpha = float(incremental_alpha or 0.0)
    comp = float(complexity_delta or 0.0)
    risk = float(data_risk or 0.0)
    reasons = []
    if abs(alpha) <= 0.005:
        reasons.append("INCREMENTAL_ALPHA_ZERO")
    if comp > 0.05:
        reasons.append("COMPLEXITY_UP")
    if risk > 0.3:
        reasons.append("DATA_RISK_UP")
    if len(reasons) >= 2:
        action = "RETIRE"
    elif reasons:
        action = "REVIEW"
    else:
        action = "KEEP"
    return {"module": module,
            "incremental_alpha": round(alpha, 4),
            "complexity_delta": round(comp, 4),
            "data_risk": round(risk, 4),
            "action": action,
            "reasons": reasons}


def advance_module_lifecycle(current, target) -> str:
    """模块生命周期推进（只进不退）。"""
    if current not in MODULE_LIFECYCLE or target not in MODULE_LIFECYCLE:
        raise ValueError(f"非法模块状态 {current}→{target}")
    if MODULE_LIFECYCLE.index(target) < MODULE_LIFECYCLE.index(current):
        raise ValueError(f"禁止回退模块状态 {current}→{target}")
    return target
