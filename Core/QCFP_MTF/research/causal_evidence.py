# coding: utf-8
"""Causal Attribution Layer（QCFP-MTF 2.8：43 号因果证据等级）

把 Correlation 与 Causal Evidence 明确分开：
    L0 Observation → L1 Correlation → L2 Conditional Relationship →
    L3 Robust OOS Relationship → L4 Quasi-Causal Evidence →
    L5 Causal Hypothesis Supported

报告措辞随证据等级调整（不写"机构资金流导致上涨"，
写"机构资金流与未来收益存在稳定的条件相关关系"）。
"""


EVIDENCE_LEVELS = (
    "L0_observation", "L1_correlation", "L2_conditional",
    "L3_robust_oos", "L4_quasi_causal", "L5_causal_supported",
)


def causal_evidence_level(oos_consistent=False, ablation_ok=False,
                          counterfactual_ok=False,
                          matched_sample_ok=False,
                          mechanism_supported=False) -> dict:
    """证据等级判定。"""
    if mechanism_supported and counterfactual_ok \
            and matched_sample_ok and oos_consistent and ablation_ok:
        level = "L5_causal_supported"
    elif counterfactual_ok and matched_sample_ok and oos_consistent:
        level = "L4_quasi_causal"
    elif oos_consistent and ablation_ok:
        level = "L3_robust_oos"
    elif oos_consistent:
        level = "L2_conditional"
    elif oos_consistent or ablation_ok:
        level = "L1_correlation"
    else:
        level = "L0_observation"
    return {"level": level,
            "recommended_wording": _wording(level)}


def _wording(level) -> str:
    if level >= "L4_quasi_causal":
        return "存在准因果证据：控制混淆后关系仍成立"
    if level == "L3_robust_oos":
        return "存在稳健的 OOS 条件相关关系"
    if level == "L2_conditional":
        return "存在稳定的条件相关关系"
    if level == "L1_correlation":
        return "存在相关性（不构成因果）"
    return "仅为观察现象（无证据等级）"
