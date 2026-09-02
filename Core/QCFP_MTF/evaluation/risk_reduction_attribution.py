# coding: utf-8
"""Risk Reduction Attribution（QCFP-MTF 2.8：75 号风险削减归因）

单独证明风险治理到底减少了什么风险，拆解为：
    Drawdown avoided / Tail loss avoided / Concentration reduced /
    Liquidity risk reduced / Gap risk reduced / Turnover cost reduced

验收标准：风险模块至少能证明一种独立风险贡献，
否则进入简化评估。
"""


RISK_DIMENSIONS = ("drawdown_avoided", "tail_loss_avoided",
                   "concentration_reduced", "liquidity_risk_reduced",
                   "gap_risk_reduced", "turnover_cost_reduced")


def risk_reduction_attribution(attributions: dict,
                               min_contribution: float = 0.005) -> dict:
    """attributions：{layer: {dimension: value}}（value>0 表示该维度降低）。"""
    results = {}
    for layer, dims in (attributions or {}).items():
        contributions = {d: round(float(dims.get(d) or 0.0), 4)
                         for d in RISK_DIMENSIONS
                         if float(dims.get(d) or 0.0) > min_contribution}
        has = bool(contributions)
        results[layer] = {
            "contributions": contributions,
            "independent_risk_contribution": has,
            "verdict": "HAS_CONTRIBUTION" if has
            else "NO_CONTRIBUTION",
        }
    return {"results": results,
            "rule": "风险模块至少证明一种独立风险贡献，"
                    "否则进入简化评估"}


def risk_module_necessity(layer, contribution: bool,
                          other_evidence: float = 0.0) -> dict:
    if contribution:
        return {"module": layer, "verdict": "KEEP",
                "reason": "具备独立风险贡献"}
    if abs(float(other_evidence)) > 0.005:
        return {"module": layer, "verdict": "REVIEW",
                "reason": "无直接风险贡献但有其他证据 → 复核"}
    return {"module": layer, "verdict": "SIMPLIFICATION_REVIEW",
            "reason": "无独立风险贡献且无其他证据 → 简化评估"}


def risk_module_verdict(module, risk_reduction, ablation_value,
                        duplicate_coverage) -> dict:
    """新 75 号：风险模块至少证明一种 Independent Risk Reduction；
    risk reduction=0 + ablation=0 + duplicate coverage>0 → 删除流程。"""
    rr = float(risk_reduction or 0.0)
    abl = float(ablation_value or 0.0)
    dup = float(duplicate_coverage or 0.0)
    if rr <= 0.005 and abs(abl) <= 0.005 and dup > 0.005:
        return {"module": module, "verdict": "DELETE_REVIEW",
                "reason": "risk reduction=0 + ablation=0 + "
                          "duplicate coverage>0 → 删除流程",
                "delete": True}
    if rr <= 0.005:
        return {"module": module, "verdict": "REVIEW",
                "reason": "无独立风险削减证据 → 复核",
                "delete": False}
    return {"module": module, "verdict": "KEEP",
            "reason": "具备独立风险削减",
            "delete": False}
