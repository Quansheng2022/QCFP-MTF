# coding: utf-8
"""Production Dependency Allowlist（QCFP-MTF 2.8：新 49 号）

Production 允许 import 的包用白名单控制——没被批准的 Production
dependency 默认禁止（UNKNOWN must degrade）。

禁止：wave.outcome_label / research.* / ablation.* / future_label.* /
      legacy.* / report.*

验收标准：Production dependency graph 中
Research-only dependency count = 0、Legacy authority dependency count = 0。
"""


PRODUCTION_ALLOWED_PREFIXES = (
    "data.", "institutional", "wave.asof", "decision.", "risk",
    "portfolio", "execution", "ledger", "safety", "governance",
    "common.", "config.", "market.",
)

FORBIDDEN_PREFIXES = (
    "wave.outcome", "research.", "ablation.", "future_label.",
    "legacy.", "report.",
)


def dependency_allowlist_check(dependencies) -> dict:
    """dependencies：生产依赖列表（模块/包名）。"""
    violations = []
    for dep in dependencies or []:
        d = str(dep)
        if any(d.startswith(p) for p in FORBIDDEN_PREFIXES):
            violations.append({"dependency": d, "reason": "FORBIDDEN_PREFIX"})
        elif not any(d.startswith(p) or d == p.rstrip(".")
                     for p in PRODUCTION_ALLOWED_PREFIXES):
            violations.append({"dependency": d,
                               "reason": "NOT_ALLOWLISTED"})
    research_count = sum(1 for v in violations
                         if v["dependency"].startswith("research."))
    legacy_count = sum(1 for v in violations
                       if v["dependency"].startswith("legacy."))
    return {
        "violations": violations,
        "research_only_dependency_count": research_count,
        "legacy_authority_dependency_count": legacy_count,
        "allowed": not violations,
        "ci_verdict": "PASS" if not violations else "FAIL",
        "rule": "没被批准的 Production dependency → 默认禁止",
    }
