# coding: utf-8
"""Evidence Contradiction Handling（QCFP-MTF 2.8：94 号证据矛盾处理）

研究证据不会永远一致。不再靠一个综合 score 掩盖冲突，而是输出：
    SUPPORTING / CONTRADICTING / INCONCLUSIVE
并显式保存 trade-off。

验收标准：重大冲突不能被自动平均成一个分数；
QCFP_MTF 的原则本来就是 Risk > Return。
"""


def evidence_contradiction_handling(evidence: dict) -> dict:
    """evidence：{dimension: {"verdict": "SUPPORTING"/"CONTRADICTING"/
    "INCONCLUSIVE", "strength": "STRONG"/"MILD"}}"""
    supporting = [d for d, v in (evidence or {}).items()
                  if v.get("verdict") == "SUPPORTING"]
    contradicting = [d for d, v in (evidence or {}).items()
                     if v.get("verdict") == "CONTRADICTING"]
    inconclusive = [d for d, v in (evidence or {}).items()
                    if v.get("verdict") == "INCONCLUSIVE"]
    return {
        "supporting": supporting,
        "contradicting": contradicting,
        "inconclusive": inconclusive,
        "conflict": bool(supporting and contradicting),
        "trade_offs": {d: (evidence or {}).get(d, {}).get("strength")
                       for d in contradicting},
        "auto_average_forbidden": bool(supporting and contradicting),
        "rule": "重大冲突不能被自动平均成一个分数",
    }


def conclude_evidence(handling: dict, risk_positive=False,
                      return_negative=False,
                      risk_mandate_dominates=True) -> dict:
    """结合 Risk>Return 原则给出结论。"""
    if not handling.get("conflict"):
        return {"conclusion": "KEEP" if handling.get("supporting")
                else "REVIEW",
                "reason": "证据方向一致或不足"}
    if risk_positive and return_negative and risk_mandate_dominates:
        return {"conclusion": "KEEP",
                "reason": "risk mandate dominates return loss"}
    return {"conclusion": "REVIEW",
            "reason": "证据冲突且风险与收益方向同向恶化 → 复核"}


def strong_conflicts(handling: dict) -> list:
    """新 94 号：强 CONTRADICTING 证据必须保留到 Research Review /
    Promotion Report，不能被平均掉。"""
    conflicts = []
    for dim, verdict in (handling.get("evidence") or {}).items():
        if verdict.get("verdict") == "CONTRADICTING" \
                and verdict.get("strength") == "STRONG":
            conflicts.append(dim)
    return conflicts


def contradiction_promotion_report(evidence: dict) -> dict:
    """新 94 号：任何强 CONTRADICTING 证据都必须保留到报告。"""
    handling = evidence_contradiction_handling(evidence)
    handling["evidence"] = evidence
    conflicts = strong_conflicts(handling)
    return {
        "conflicts_preserved": conflicts,
        "promotion_verdict": "REVIEW_REQUIRED" if conflicts
        else "PROMOTION_OK",
        "rule": "Risk > Return ≠ 所有指标平均；"
                "强冲突必须显式保留",
        "auto_average_forbidden": True,
    }
