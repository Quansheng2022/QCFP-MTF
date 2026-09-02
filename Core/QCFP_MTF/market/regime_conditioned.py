# coding: utf-8
"""Regime-conditioned Decision（QCFP-MTF 2.8：13 号市场状态条件决策）

Regime 提升为独立一级状态变量：
    Regime → Permission Modifier ↓ / Wave Threshold ↑ / Risk Budget ↓ /
             Position Size ↓

硬约束：Regime 不能提高 Permission（只能降低），
    Institutional Permission > Regime > Wave。
"""


REGIME_MODIFIERS = {
    "Bull": {"permission_scale": 1.0, "wave_threshold_up": 1.0,
             "risk_budget_scale": 1.0, "position_scale": 1.0},
    "Sideway": {"permission_scale": 0.8, "wave_threshold_up": 1.1,
                "risk_budget_scale": 0.8, "position_scale": 0.8},
    "Bear": {"permission_scale": 0.5, "wave_threshold_up": 1.2,
             "risk_budget_scale": 0.5, "position_scale": 0.5},
    "HighVolatility": {"permission_scale": 0.6, "wave_threshold_up": 1.15,
                       "risk_budget_scale": 0.6, "position_scale": 0.6},
    "LiquidityStress": {"permission_scale": 0.4, "wave_threshold_up": 1.3,
                        "risk_budget_scale": 0.4, "position_scale": 0.4},
    "Transition": {"permission_scale": 0.7, "wave_threshold_up": 1.1,
                   "risk_budget_scale": 0.7, "position_scale": 0.7},
    "Crisis": {"permission_scale": 0.2, "wave_threshold_up": 1.5,
               "risk_budget_scale": 0.2, "position_scale": 0.2},
}


def regime_conditioned_modifiers(regime, permission="ALLOW") -> dict:
    """Regime 条件修饰符。

    返回 permission_scale（只降不升）+ wave_threshold_up +
    risk_budget_scale + position_scale。
    """
    m = REGIME_MODIFIERS.get(regime, REGIME_MODIFIERS["Sideway"])
    # Regime 不能提高 Permission：scale ≤ 1 恒成立
    return {"regime": regime,
            "permission": permission,
            "permission_scale": m["permission_scale"],
            "wave_threshold_up": m["wave_threshold_up"],
            "risk_budget_scale": m["risk_budget_scale"],
            "position_scale": m["position_scale"],
            "permission_never_raised": m["permission_scale"] <= 1.0}


def regime_adjusted_permission(permission, regime) -> dict:
    """按 Regime 调整权限强度（只降不升）。"""
    from ..decision.permission_gate import permission_strength
    m = regime_conditioned_modifiers(regime, permission)
    strength = permission_strength(permission)
    adjusted = strength * m["permission_scale"]
    return {"permission": permission,
            "regime": regime,
            "base_strength": round(strength, 4),
            "adjusted_strength": round(adjusted, 4),
            "adjusted_strength_leq_base": adjusted <= strength + 1e-9}
