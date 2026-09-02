# coding: utf-8
"""Multiple Testing / Overfitting Firewall（QCFP-MTF 2.8：34 号反过拟合防火墙）

记录：Number of Experiments / Parameter Searches / Model Variants /
      Feature Variants / Selection Bias / Data Snooping Risk

区分"发现的 Alpha"与"筛选出来的 Alpha"：
    实验越多、选择越宽松 → Data Snooping Risk 越高 → 防火墙收紧。
"""


def overfitting_firewall(n_experiments=0, n_parameter_searches=0,
                         n_model_variants=0, n_feature_variants=0,
                         selection_rule="best", holdout_locked=False) -> dict:
    """反过拟合防火墙。

    data_snooping_risk 0-1：
        +0.3 每 100 实验；+0.2 每 100 参数搜索；+0.15 每 50 模型变体；
        +0.15 每 50 特征变体；best 选择 +0.2；holdout 锁定 −0.4。
    """
    risk = (0.3 * n_experiments / 100.0
            + 0.2 * n_parameter_searches / 100.0
            + 0.15 * n_model_variants / 50.0
            + 0.15 * n_feature_variants / 50.0)
    if selection_rule in ("best", "best_ci"):
        risk += 0.2
    if holdout_locked:
        risk -= 0.4
    risk = max(0.0, min(1.0, risk))
    if risk >= 0.6:
        verdict = "HIGH_SNOOPING"
    elif risk >= 0.3:
        verdict = "MODERATE"
    else:
        verdict = "LOW"
    return {
        "n_experiments": n_experiments,
        "n_parameter_searches": n_parameter_searches,
        "n_model_variants": n_model_variants,
        "n_feature_variants": n_feature_variants,
        "selection_rule": selection_rule,
        "holdout_locked": holdout_locked,
        "data_snooping_risk": round(risk, 4),
        "verdict": verdict,
        "firewall_blocked": verdict == "HIGH_SNOOPING",
    }
