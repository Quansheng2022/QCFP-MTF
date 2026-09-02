# coding: utf-8
"""Certification Scope（QCFP-MTF 2.8：92 号认证范围）

防止"一个测试通过代表整个系统通过"。每张 Certificate 必须明确 scope：
    component / strategy_version / config_hash / dataset_snapshot /
    universe / time_range / market / frequency / feature_manifest

验收标准：认证不允许跨市场、数据、配置、Feature Set、时间频率
自动继承。
"""


SCOPE_FIELDS = ("component", "strategy_version", "config_hash",
                "dataset_snapshot", "universe", "time_range", "market",
                "frequency", "feature_manifest")


def certification_scope(certificate_scope: dict,
                        claim_scope: dict) -> dict:
    """certificate_scope：证书覆盖范围；claim_scope：声称应用范围。
    逐字段比对，任一不一致 → NOT_COVERED。"""
    mismatches = []
    for field in SCOPE_FIELDS:
        cert = certificate_scope.get(field)
        claim = claim_scope.get(field)
        if cert != claim:
            mismatches.append({"field": field,
                               "certified": cert,
                               "claimed": claim})
    return {
        "mismatches": mismatches,
        "covers": not mismatches,
        "verdict": "CERTIFIED" if not mismatches else "NOT_COVERED",
        "rule": "认证不允许跨市场/数据/配置/Feature/频率自动继承",
    }


def claim_within_certified(certified_scope: dict,
                           claim_scope: dict) -> dict:
    """新 92 号：所有 Production Certificate 必须 ClaimScope ⊆
    CertifiedScope，否则 NOT_CERTIFIED。"""
    mismatches = []
    for field in SCOPE_FIELDS:
        cert = certified_scope.get(field)
        claim = claim_scope.get(field)
        if cert != claim:
            mismatches.append({"field": field,
                               "certified": cert,
                               "claimed": claim})
    return {
        "mismatches": mismatches,
        "claim_within_certified": not mismatches,
        "verdict": "CERTIFIED" if not mismatches else "NOT_CERTIFIED",
        "rule": "验证的是一个明确系统实例，不是一个模糊模型名字；"
                "ClaimScope ⊆ CertifiedScope",
    }
