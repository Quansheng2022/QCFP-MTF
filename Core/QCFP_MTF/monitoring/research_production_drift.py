# coding: utf-8
"""Research → Production Drift（QCFP-MTF 2.8：37 号研究-生产漂移检测）

监测 Research 认证时分布与 Production 实际分布是否显著变化：
    Wave stage / holding period / turnover / permission distribution /
    execution cost / capture ratio

禁止自动调参；正确链条：
    Detect → Evidence → Review → Candidate → Shadow → Human Approval →
    Production
"""


def research_production_drift(research_dist, production_dist,
                              dim="wave_stage") -> dict:
    """分布漂移（PSI 风格简化）。

    research_dist/production_dist：{bucket: 占比}（归一化）
    """
    keys = set(research_dist) | set(production_dist)
    total_r = sum(research_dist.values()) or 1.0
    total_p = sum(production_dist.values()) or 1.0
    psi = 0.0
    for k in keys:
        p_r = (research_dist.get(k, 0.0) or 0.0) / total_r
        p_p = (production_dist.get(k, 0.0) or 0.0) / total_p
        p_r = max(1e-4, p_r)
        p_p = max(1e-4, p_p)
        psi += (p_r - p_p) * (p_p / p_r - 1.0) * 0.5
    psi = round(abs(psi), 4)
    if psi >= 0.25:
        severity = "HIGH_DRIFT"
    elif psi >= 0.10:
        severity = "MODERATE"
    else:
        severity = "LOW"
    return {
        "dimension": dim,
        "psi": psi,
        "severity": severity,
        "action": "REVIEW_ONLY" if severity != "LOW" else "CONTINUE",
        "governance_chain": ("DETECT", "EVIDENCE", "REVIEW", "CANDIDATE",
                             "SHADOW", "HUMAN_APPROVAL", "PRODUCTION"),
        "auto_retrain_forbidden": True,
        "note": "漂移≠自动重训；必须走治理链",
    }


def drift_lifecycle_transition(drift_report: dict) -> dict:
    """新 37 号：Drift 真正改变生命周期状态，而不是只写报告。

    严重 drift → NORMAL → REVIEW_REQUIRED（触发 revalidation），
    禁止自动改参数。
    """
    severity = drift_report.get("severity") or "LOW"
    if severity == "HIGH_DRIFT":
        state, action = "REVIEW_REQUIRED", "REVALIDATION_TRIGGERED"
    elif severity == "MODERATE":
        state, action = "WATCH", "EVIDENCE_REVIEW"
    else:
        state, action = "NORMAL", "CONTINUE"
    return {
        "lifecycle_state": state,
        "action": action,
        "revalidation_required": severity == "HIGH_DRIFT",
        "auto_param_modify_forbidden": True,
        "chain": "Detect → Evidence → Review → Candidate → Shadow → "
                 "Human Approval → Production",
    }
