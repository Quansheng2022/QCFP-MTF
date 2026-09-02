# coding: utf-8
"""Causal / Incremental Evidence Engine（QCFP-MTF 2.7）

从"模块有效"升级到"模块在什么条件下、通过什么机制产生价值"：
    risk_reduction：MDD/MAE 改善显著（风险过滤价值）
    alpha：收益/捕获改善显著
    mixed：两者兼有
    neutral：无显著增量（复杂度预算标记 REVIEW/DROP）
"""

from .marginal import marginal_utility_matrix


def evidence_verdict(m, mdd_thr=0.02, ret_thr=0.005) -> str:
    mdd_d = abs(m.get("mdd_delta") or 0.0)
    ret_d = abs(m.get("return_delta") or 0.0)
    cap_d = abs(m.get("capture_delta") or 0.0)
    risk_ok = mdd_d >= mdd_thr
    alpha_ok = (ret_d >= ret_thr) or (cap_d >= ret_thr)
    if risk_ok and alpha_ok:
        return "mixed"
    if risk_ok:
        return "risk_reduction"
    if alpha_ok:
        return "alpha"
    return "neutral"


def incremental_evidence(abl_json, mdd_thr=0.02, ret_thr=0.005) -> dict:
    matrix = marginal_utility_matrix(abl_json)
    out = {}
    for k, m in matrix.items():
        out[k] = {"class": m.get("class"), "verdict": evidence_verdict(
            m, mdd_thr=mdd_thr, ret_thr=ret_thr), "deltas": m}
    return out


def incremental_alpha(base_metrics, new_metrics, module_name="new_module",
                      ret_thr=0.005, sharpe_thr=0.1) -> dict:
    """增量 Alpha 验证（83 号）：
        Base vs Base+New Module
    比较 ΔReturn / ΔSharpe / ΔMFE Capture / ΔMDD / ΔTurnover / ΔCost /
    ΔTail Risk → Incremental Alpha + 删除建议。
    """
    fields = ("return", "sharpe", "mfe_capture", "mdd", "turnover",
              "cost", "tail_risk")
    deltas = {}
    for f in fields:
        b = float(base_metrics.get(f) or 0.0)
        n = float(new_metrics.get(f) or 0.0)
        deltas[f] = round(n - b, 4)
    ret_alpha = deltas["return"]
    sharpe_alpha = deltas["sharpe"]
    capture_alpha = deltas["mfe_capture"]
    # 收益改善但回撤/成本恶化 → 需扣减
    risk_penalty = max(0.0, deltas["mdd"] + deltas["tail_risk"])
    cost_penalty = max(0.0, deltas["cost"] + deltas["turnover"] * 0.01)
    net_alpha = ret_alpha - risk_penalty - cost_penalty
    verdict = "INCREMENTAL_ALPHA" if (
        net_alpha >= ret_thr and sharpe_alpha >= -sharpe_thr) else \
        "NEUTRAL" if abs(net_alpha) < ret_thr else "DETRIMENTAL"
    return {
        "module": module_name,
        "deltas": deltas,
        "net_alpha": round(net_alpha, 4),
        "verdict": verdict,
        "recommendation": "KEEP" if verdict == "INCREMENTAL_ALPHA" else
        "REVIEW" if verdict == "NEUTRAL" else "DELETE",
    }


def causal_attribution(observed_effect, incremental_effect,
                       regime_effect=0.0, matched_sample_effect=None) -> dict:
    """因果归因层（84 号）：
        Observed Effect vs Incremental Effect（剔除市场/行业/风格暴露）。

    输出归因为"真实模块贡献"的比例；若 matched_sample_effect 提供，
    则用匹配样本效应作为增量（更严格）。
    """
    obs = float(observed_effect or 0.0)
    inc = float(incremental_effect if incremental_effect is not None
                else matched_sample_effect or 0.0)
    reg = float(regime_effect or 0.0)
    attributable = inc
    if abs(obs) > 1e-9:
        share = attributable / obs
    else:
        share = 0.0
    environment_share = 1.0 - share
    return {
        "observed_effect": round(obs, 4),
        "incremental_effect": round(inc, 4),
        "regime_effect": round(reg, 4),
        "attributable_share": round(share, 4),
        "environment_share": round(environment_share, 4),
        "conclusion": "MODULE_CAUSAL" if share >= 0.5 else
        "ENVIRONMENT_DRIVEN",
    }
