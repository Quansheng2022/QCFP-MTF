# coding: utf-8
"""Complexity Budget（QCFP-MTF 2.8：32 号复杂度资本管制）

每新增/保留一个模块，必须通过 Ablation 证明存在统计稳定的增量价值：
    KEEP    至少一个维度显著（收益↑ 或 MDD↓ 或 捕获↑ 或 换手↓）
    REVIEW  只有微弱变化（可观察但不足以证明）
    DROP    无变化（复杂度增加、效用≈0）
"""

from ..ablation.marginal import marginal_utility_matrix


def _verdict(m: dict, min_delta: float) -> str:
    deltas = [m.get("return_delta"), m.get("mdd_delta"),
              m.get("capture_delta"), m.get("turnover_delta")]
    if all(d is None for d in deltas):
        return "NO_DATA"
    max_abs = max((abs(d) for d in deltas if d is not None), default=0.0)
    if max_abs < min_delta:
        return "DROP" if max_abs == 0.0 else "REVIEW"
    return "KEEP"


def complexity_budget(abl_json: dict, min_delta: float = 0.005) -> dict:
    matrix = marginal_utility_matrix(abl_json)
    verdicts = {k: _verdict(v, min_delta) for k, v in matrix.items()}
    keep = sum(1 for v in verdicts.values() if v == "KEEP")
    total = len(verdicts)
    return {
        "verdicts": verdicts,
        "keep": keep,
        "total": total,
        "complexity_score": round(keep / total, 2) if total else None,
        "drop_candidates": [k for k, v in verdicts.items()
                            if v in ("REVIEW", "DROP", "NO_DATA")],
    }


DEFAULT_BUDGET_LIMITS = {
    "max_features": 80,
    "max_core_rules": 40,
    "max_free_parameters": 25,
    "max_exceptions": 10,
    "max_decision_branches": 50,
}


def budget_consumption(usage: dict, limits=None) -> dict:
    """复杂度消耗核算（32 号）：
        新增模块必须说明消耗了多少 Complexity Budget。

    usage：{features: n, core_rules: n, free_parameters: n,
            exceptions: n, decision_branches: n}
    """
    limits = limits or DEFAULT_BUDGET_LIMITS
    out = {}
    over = []
    for key, limit in limits.items():
        usage_key = key.replace("max_", "")
        used = int(usage.get(usage_key, 0))
        out[key] = {"limit": limit, "used": used,
                    "remaining": max(0, limit - used),
                    "over": used > limit}
        if used > limit:
            over.append(key)
    return {"consumption": out, "over_budget": over,
            "within_budget": not over}
