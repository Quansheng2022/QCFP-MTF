# coding: utf-8
"""Evidence Expiry Policy（QCFP-MTF 2.8：82 号研究证据过期策略）

管理研究证据本身何时失效。ValidationCertificate 记录：
    evidence_start / evidence_end / market_regimes_covered /
    sample_size / certificate_expiry

正确逻辑（不是机械重训）：
    Evidence expired → Certification downgraded → Revalidation
    → Research → Shadow → Approval（不自动改参数）
"""


def _ym_to_months(ym: str) -> int:
    try:
        year, month = str(ym).split("-")
        return int(year) * 12 + int(month)
    except (ValueError, AttributeError):
        return 0


def evidence_expiry_policy(certificate: dict, as_of="2026-08") -> dict:
    """certificate：{evidence_start, evidence_end,
    market_regimes_covered, sample_size, certificate_expiry}"""
    expiry = str(certificate.get("certificate_expiry") or "")
    months_left = _ym_to_months(expiry) - _ym_to_months(as_of)
    if months_left < 0:
        freshness, certification = "EXPIRED", "INSUFFICIENT"
    elif months_left <= 6:
        freshness, certification = "AGING", "DOWNGRADED"
    else:
        freshness, certification = "FRESH", "CERTIFIED"
    return {
        "evidence_start": certificate.get("evidence_start"),
        "evidence_end": certificate.get("evidence_end"),
        "market_regimes_covered":
            certificate.get("market_regimes_covered"),
        "sample_size": certificate.get("sample_size"),
        "certificate_expiry": expiry,
        "months_until_expiry": months_left,
        "freshness": freshness,
        "certification_status": certification,
        "revalidation_required": freshness != "FRESH",
        "auto_param_modify_forbidden": True,
        "chain": "Evidence expired → Certification downgraded → "
                 "Revalidation → Research → Shadow → Approval",
    }


def expired_certificate_block(expiry_result: dict,
                              release_id: str = "") -> dict:
    """新 82 号：Expired Certificate 不能继续为新 Production Release
    提供有效认证。"""
    status = expiry_result.get("certification_status")
    if status in ("INSUFFICIENT", "DOWNGRADED"):
        return {"release_id": release_id,
                "certificate_valid": False,
                "verdict": "RELEASE_BLOCKED",
                "reason": f"证书 {status} → 不能为新 Release 提供认证",
                "allowed": False}
    return {"release_id": release_id,
            "certificate_valid": True,
            "verdict": "RELEASE_OK",
            "allowed": True}


def evidence_pack_certificate_valid(pack: dict, certificate: dict) -> dict:
    """新 82 号：EvidencePack 绑定证书——证书过期则证据包失效。"""
    expiry = evidence_expiry_policy(certificate)
    if expiry["certification_status"] in ("INSUFFICIENT", "DOWNGRADED"):
        return {"evidence_pack_id": pack.get("evidence_hash"),
                "valid": False,
                "verdict": "EVIDENCE_PACK_EXPIRED",
                "rule": "Expired Certificate 不能继续提供有效认证"}
    return {"evidence_pack_id": pack.get("evidence_hash"),
            "valid": True, "verdict": "EVIDENCE_PACK_VALID"}
