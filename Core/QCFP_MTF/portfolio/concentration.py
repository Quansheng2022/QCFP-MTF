# coding: utf-8
"""Portfolio Concentration Governor（QCFP-MTF 2.8：77 号集中度治理器）

单股都合规 ≠ 组合合规：
    A=4% + B=4% + C=4% + D=4%，但同行业/同主题/同 Beta
    → 实际相当于 16% 集中下注。

维度：Symbol / Sector / Theme / Factor / Correlation / Beta /
      Institutional Exposure → Effective Concentration
"""

from .exposure_engine import effective_risk_exposure, group_exposure


def effective_concentration(positions, corr_matrix=None,
                            concentration_cap=0.25) -> dict:
    """有效集中度 + 治理结论。

    指标：
        max_sector / max_theme / beta 离散度 / ENB / 相关性调整暴露
    治理：
        任一维度超过阈值 → concentration_scale < 1（组合新增收缩）。
    """
    weights = [float(p.get("weight") or 0.0) for p in positions]
    total = sum(weights)
    sector = group_exposure(positions, "sector")
    theme = group_exposure(positions, "theme")
    eff = effective_risk_exposure(positions, corr_matrix=corr_matrix)
    max_sector = max(sector.values()) if sector else 0.0
    max_theme = max(theme.values()) if theme else 0.0
    betas = [abs(float(p.get("beta") or 1.0)) for p in positions]
    beta_max = max(betas) if betas else 1.0
    beta_min = min(betas) if betas else 1.0
    beta_dispersion = beta_max / max(beta_min, 1e-9)
    flags = []
    if max_sector >= 0.5:
        flags.append(f"SECTOR_CONCENTRATED({max_sector:.0%})")
    if max_theme >= 0.4:
        flags.append(f"THEME_CONCENTRATED({max_theme:.0%})")
    if beta_dispersion <= 1.3:
        flags.append(f"BETA_HOMOGENEOUS({beta_dispersion:.2f})")
    if eff["reduction_pct"] < 0.2:
        flags.append(f"LOW_DIVERSIFICATION(red={eff['reduction_pct']:.0%})")
    scale = 1.0
    if max_sector >= 0.5 or max_theme >= 0.4:
        scale = min(scale, float(concentration_cap) / max(
            max_sector, max_theme, 1e-9))
    if beta_dispersion <= 1.3:
        scale = min(scale, 0.7)
    return {
        "total_exposure": round(total, 4),
        "max_sector": round(max_sector, 4),
        "max_theme": round(max_theme, 4),
        "beta_dispersion": round(beta_dispersion, 4),
        "effective_risk_exposure": eff,
        "effective_concentration": round(
            max_sector if max_sector >= max_theme else max_theme, 4),
        "concentration_scale": round(scale, 4),
        "flags": flags,
        "restricted": scale < 1.0,
    }
