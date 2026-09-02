# coding: utf-8
"""Minimum Viable Canonical Model（QCFP-MTF 2.8：59 号最小有效系统）

主动寻找最小有效系统：极简核心候选
    PIT Evidence → Permission → Wave → FSM → Risk/Position Cap →
    Final Target → Ledger
与完整系统做长期 OOS/Ablation 比较。

验收标准：每次大版本都应回答
"当前最小还能保持 95%–100% 实战价值的 Canonical 系统是什么？"
"""


MINIMAL_CANONICAL_STAGES = (
    "PIT_EVIDENCE", "PERMISSION", "WAVE", "FSM",
    "RISK_POSITION_CAP", "FINAL_TARGET", "LEDGER",
)

VALUE_DIMENSIONS = ("sharpe", "mdd", "wave_capture", "practicality")


def _dimension_value(metrics: dict, key: str) -> float:
    v = float(metrics.get(key) or 0.0)
    return abs(v) if key == "mdd" else max(0.0, v)


def minimum_viable_canonical(full_metrics: dict, minimal_metrics: dict,
                             retention_target: float = 0.95) -> dict:
    """价值保留率：minimal 相对 full 在各维度保持的比例。"""
    retentions = {}
    for key in VALUE_DIMENSIONS:
        f = _dimension_value(full_metrics, key)
        m = _dimension_value(minimal_metrics, key)
        retentions[key] = round(min(1.0, m / f), 4) if f else None
    valid = [v for v in retentions.values() if v is not None]
    overall = round(sum(valid) / len(valid), 4) if valid else None
    meet = overall is not None and overall >= retention_target
    return {
        "minimal_canonical_stages": list(MINIMAL_CANONICAL_STAGES),
        "retentions": retentions,
        "overall_value_retention": overall,
        "retention_target": retention_target,
        "verdict": "MINIMAL_SUFFICIENT" if meet else "FULL_REQUIRED",
        "recommendation": ("优先保留更小的 Minimum Canonical"
                           if meet else "完整系统仍有必要"),
    }


def minimum_canonical_recommendation(full_metrics: dict,
                                     minimal_metrics: dict,
                                     full_complexity=1.0,
                                     minimal_complexity=1.0,
                                     retention_target=0.95) -> dict:
    """新 59 号：每个大版本回答"当前最小可信 Canonical Core 是什么"。

    若 Minimal 保留 ≥95% 实战价值且复杂度只有 Full 一半 → 优先简化。
    """
    r = minimum_viable_canonical(full_metrics, minimal_metrics,
                                 retention_target=retention_target)
    complexity_ratio = round(
        float(minimal_complexity) / max(float(full_complexity), 1e-9), 2)
    if r["verdict"] == "MINIMAL_SUFFICIENT" and complexity_ratio <= 0.6:
        verdict = "SIMPLIFY"
        reason = (f"Minimal 保留 {r['overall_value_retention']:.0%} 实战价值"
                  f"且复杂度仅为 Full 的 {complexity_ratio:.0%} → 简化")
    elif r["verdict"] == "MINIMAL_SUFFICIENT":
        verdict = "MINIMAL_ELIGIBLE"
        reason = "Minimal 保留足够价值，可作为候选核心"
    else:
        verdict = "FULL_REQUIRED"
        reason = "Minimal 价值保留不足，完整系统仍有必要"
    return {"verdict": verdict, "reason": reason,
            "overall_value_retention": r["overall_value_retention"],
            "complexity_ratio": complexity_ratio,
            "minimal_canonical_core":
                list(MINIMAL_CANONICAL_STAGES)}


def major_release_minimal_answer(full_metrics: dict,
                                 minimal_metrics: dict,
                                 full_complexity=1.0,
                                 minimal_complexity=1.0) -> dict:
    """Release 3（新 29 号）：每个 Major Release 必须给出
    MINIMAL_SUFFICIENT 或 FULL_REQUIRED，不能没有答案。"""
    r = minimum_canonical_recommendation(full_metrics, minimal_metrics,
                                         full_complexity,
                                         minimal_complexity)
    return {"answer": r["verdict"],
            "value_retention": r["overall_value_retention"],
            "complexity_ratio": r["complexity_ratio"],
            "required": True,
            "rule": "每个大版本必须回答'当前最小还能保持 95%–100% "
                    "实战价值的 Canonical 系统是什么'"}
