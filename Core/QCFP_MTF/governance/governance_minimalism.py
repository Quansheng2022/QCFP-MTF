# coding: utf-8
"""Governance Minimalism Test（QCFP-MTF 2.8：98 号治理自身瘦身测试）

审查治理系统本身是否也变得过度复杂：
    Can these 4 registries be one table?
    Can these 3 certificates share one schema?
    Can these 5 checks run in one gate?

目标：Minimum governance components，
同时保留 audit / replay / PIT / authority / certification。
治理复杂度本身也进入 Complexity Budget——
不能为了治理复杂度，再制造另一套复杂度。
"""


def governance_minimalism_test(registries=None, certificates=None,
                               checks=None) -> dict:
    registries = list(registries or [])
    certificates = list(certificates or [])
    checks = list(checks or [])
    suggestions = []
    if len(registries) >= 4:
        suggestions.append(f"{len(registries)} 个 registry "
                           "→ 考虑合并为一张表/一个服务")
    if len(certificates) >= 3:
        suggestions.append(f"{len(certificates)} 种 certificate "
                           "→ 考虑共享 schema")
    if len(checks) >= 5:
        suggestions.append(f"{len(checks)} 个检查 "
                           "→ 考虑合并到同一个 gate")
    complexity = len(registries) + len(certificates) + len(checks)
    return {
        "registries": registries,
        "certificates": certificates,
        "checks": checks,
        "governance_complexity_score": complexity,
        "suggestions": suggestions,
        "verdict": "SIMPLIFY" if suggestions else "MINIMAL",
        "rule": "不能为了治理复杂度，再制造另一套复杂度；"
                "治理也进 Complexity Budget",
    }


def governance_component_verdict(component, duplicated_by=None,
                                 independent_value=0.0) -> dict:
    """新 98 号：治理组件也接受 KEEP/MERGE/DROP，不是天然永久保留。"""
    dup = bool(duplicated_by)
    value = float(independent_value or 0.0)
    if dup and value <= 0.005:
        return {"component": component, "verdict": "MERGE",
                "reason": f"与 {duplicated_by} 重复且无独立价值 → 合并",
                "action": "MERGE"}
    if value <= 0.005:
        return {"component": component, "verdict": "DROP",
                "reason": "无独立增量价值 → 删除",
                "action": "DROP"}
    return {"component": component, "verdict": "KEEP",
            "reason": "具备独立治理价值",
            "action": "KEEP"}


def governance_certificate_consolidation(certificates: list) -> dict:
    """新 98 号：Validation/Reactivation/Release/Acceptance 等证书
    检查是否真的需要多种结构，而不是每新增需求就新增一个 dataclass。"""
    certs = list(certificates or [])
    if len(certs) >= 3:
        return {"certificates": certs,
                "verdict": "CONSOLIDATE_SCHEMA",
                "suggestion": f"{len(certs)} 种证书 → 考虑共享 schema",
                "consolidation": True}
    return {"certificates": certs,
            "verdict": "MINIMAL",
            "suggestion": "证书结构数量可接受",
            "consolidation": False}
