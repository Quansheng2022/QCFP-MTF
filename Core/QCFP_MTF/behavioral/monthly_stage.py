# coding: utf-8
"""月线阶段判定：Improving / Stable / Deteriorating"""

import pandas as pd

IMPROVING_VP = {"VP_EXPANSION", "VP_LOCKED_CANDIDATE", "VP_STABLE_ASCENT"}
DETERIORATING_VP = {"VP_OVERHEAT", "VP_DIVERGENCE_HIGH", "VP_SELLING_ACTIVE",
                    "VP_PANIC", "VP_DECLINE_SILENT"}
EXTREME_T = {"T4", "T5"}


def build_monthly_stage(vp_regime: pd.Series, t_regime: pd.Series) -> pd.Series:
    """输入 m_vp_regime / turnover_liquidity_regime 对齐的 Series"""
    out = pd.Series(None, index=vp_regime.index, dtype=object)
    for i, vp in vp_regime.items():
        t = t_regime.get(i)
        if pd.isna(vp):
            out[i] = None
            continue
        if vp in IMPROVING_VP and t not in EXTREME_T:
            out[i] = "Improving"
        elif vp in DETERIORATING_VP:
            out[i] = "Deteriorating"
        else:  # SHRINK / NEUTRAL
            out[i] = "Stable"
    return out
