# coding: utf-8
"""Alpha Decay / Half-Life Engine（QCFP-MTF 2.8：46 号 Alpha 半衰期）

每个 Alpha 应知道：Age / Strength / Decay Rate / Half-Life / Stability /
Regime Dependency → Weight ↓（而不是固定 Weight=20%）。

    IC(t) = IC0 × (0.5)^(t / half_life)
"""

import math


def alpha_half_life(ic_initial, ic_current, months_elapsed) -> dict:
    """Alpha 半衰期（月）。

    half_life = months × ln(0.5) / ln(ic_current/ic_initial)
    """
    ic0 = float(ic_initial or 0.0)
    ic1 = float(ic_current or 0.0)
    months = float(months_elapsed or 0.0)
    if ic0 <= 0 or ic1 <= 0 or ic1 >= ic0:
        return {"half_life_months": None,
                "decay_rate": 0.0,
                "strength_ratio": round(ic1 / max(ic0, 1e-9), 4),
                "weight_scale": 1.0,
                "note": "无法计算半衰期（IC 未衰减或无效）"}
    ratio = ic1 / ic0
    half_life = months * math.log(0.5) / math.log(ratio)
    half_life = max(0.0, half_life)
    decay_rate = math.log(2) / half_life if half_life > 0 else 0.0
    weight_scale = min(1.0, ic1 / max(ic0, 1e-9) * 2.0)
    return {"half_life_months": round(half_life, 2),
            "decay_rate": round(decay_rate, 4),
            "strength_ratio": round(ratio, 4),
            "weight_scale": round(weight_scale, 4),
            "note": f"半衰期 {half_life:.1f} 个月 → 权重 ×{weight_scale:.2f}"}


def alpha_weight(ic_initial, ic_current, months_elapsed, base_weight) -> dict:
    """按衰减调整 Alpha 权重。"""
    hl = alpha_half_life(ic_initial, ic_current, months_elapsed)
    weight = float(base_weight or 0.0) * (hl.get("weight_scale") or 0.0)
    return {"base_weight": round(float(base_weight or 0.0), 4),
            "adjusted_weight": round(weight, 4),
            "halflife": hl}
