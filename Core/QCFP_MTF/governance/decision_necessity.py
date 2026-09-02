# coding: utf-8
"""Decision Necessity Audit（QCFP-MTF 2.8：71 号决策模块必要性审计）

比 Ablation 更进一步：不仅问"去掉后表现怎样"，还问
    - 这个模块解决什么唯一问题？
    - 是否已被其他模块覆盖？
    - 是否只是历史遗留？

每个 ACTIVE module 必须有唯一且清晰的
Purpose / Independent Value / Failure if Removed / Current Evidence；
无法说明的直接进入 REVIEW。
"""


NECESSITY_FIELDS = ("purpose", "independent_value",
                    "failure_if_removed", "current_evidence")


def decision_necessity_audit(modules: dict) -> dict:
    """modules：{module: {purpose, independent_value, failure_if_removed,
    current_evidence, covered_by?}}"""
    results = {}
    for module, attrs in (modules or {}).items():
        attrs = attrs or {}
        missing = [f for f in NECESSITY_FIELDS if not attrs.get(f)]
        covered_by = attrs.get("covered_by")
        if covered_by and not attrs.get("independent_value"):
            missing.append("independent_value(covered_by)")
        verdict = "REVIEW" if missing else "JUSTIFIED"
        results[module] = {
            "missing": missing,
            "verdict": verdict,
            "covered_by": covered_by,
            "reason": ("缺少必要说明，无法证明必须存在"
                       if missing else "具备唯一且清晰的存在理由"),
        }
    justified = sum(1 for r in results.values()
                    if r["verdict"] == "JUSTIFIED")
    return {
        "results": results,
        "justified": justified,
        "review": sum(1 for r in results.values()
                      if r["verdict"] == "REVIEW"),
        "total": len(results),
        "rule": "无法说明必要性的模块直接进入 REVIEW",
    }


def necessity_summary(audit: dict) -> dict:
    total = audit.get("total") or 0
    justified = audit.get("justified") or 0
    return {
        "justified_ratio": round(justified / total, 4) if total else None,
        "review_modules": [m for m, r in audit.get("results", {}).items()
                           if r["verdict"] == "REVIEW"],
        "recommendation": "全部模块必要性可说明" if not audit.get("review")
        else f"{audit.get('review')} 个模块缺少必要性说明 → REVIEW",
    }


def necessity_verdict(module, unique_problem, covered_by,
                      independent_impact, oos_value) -> dict:
    """新 71 号：ACTIVE Module 周期性资格审查——
        有唯一职责 + 有独立价值 → KEEP
        有价值但与其它模块高度重合 → MERGE
        没有独立价值 → DROP
        无法证明 → REVIEW
    """
    has_unique = bool(str(unique_problem or "").strip())
    covered = bool(covered_by)
    impact = float(independent_impact or 0.0)
    oos = float(oos_value or 0.0)
    independent_value = impact > 0.005 or oos > 0.005
    if has_unique and independent_value and not covered:
        verdict, reason = "KEEP", "有唯一职责 + 有独立价值"
    elif has_unique and independent_value and covered:
        verdict, reason = "MERGE", "有价值但与其他模块高度重合"
    elif not independent_value and has_unique:
        verdict, reason = "DROP", "没有独立价值"
    else:
        verdict, reason = "REVIEW", "无法证明必要性"
    return {"module": module, "verdict": verdict, "reason": reason,
            "independent_impact": round(impact, 4),
            "oos_value": round(oos, 4),
            "rule": "不能因为'这个模块一直都在'就永久 ACTIVE"}
