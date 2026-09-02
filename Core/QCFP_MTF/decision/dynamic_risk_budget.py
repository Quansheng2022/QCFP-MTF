# coding: utf-8
"""Dynamic Risk Budget Engine（QCFP-MTF 2.8：43 号动态风险预算）

风险预算随 Permission / Wave Quality / Regime / Portfolio State /
Volatility / Liquidity / Correlation 动态变化：
    Risk Budget = Base × Permission × Wave × Regime × Portfolio ×
                  Liquidity × Correlation

硬约束：Dynamic Budget ≤ Governance Hard Cap（动态只能降、不能突破硬上限）。
"""

from dataclasses import asdict, dataclass, field


PERMISSION_FACTOR = {
    "STRONG_ALLOW": 1.0, "ALLOW": 0.8, "TEST": 0.5,
    "WATCH": 0.2, "BLOCK": 0.0,
}

WAVE_FACTOR = {"STRONG": 1.0, "MEDIUM": 0.7, "WEAK": 0.4, "NONE": 0.0}

REGIME_FACTOR = {"Bull": 1.0, "Sideway": 0.8, "Bear": 0.5,
                 "HighVolatility": 0.6, "Crisis": 0.2}

PORTFOLIO_FACTOR = {"NORMAL": 1.0, "RECOVERY": 1.0, "DEFENSIVE": 0.7,
                    "CONCENTRATED": 0.6, "OVERHEATED": 0.5,
                    "RISK_OFF": 0.3}


@dataclass(frozen=True)
class DynamicRiskBudget:
    base_budget: float
    factors: dict
    dynamic_budget: float
    hard_cap: float
    final_budget: float
    capped: bool
    reasons: tuple = field(default_factory=tuple)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["reasons"] = list(self.reasons)
        return d


def _factor(mapping, key, default=0.5) -> float:
    return float(mapping.get(key, default))


def dynamic_risk_budget(base_budget, permission="WATCH", wave_quality="WEAK",
                        regime="Sideway", portfolio_state="NORMAL",
                        volatility_factor=1.0, liquidity_factor=1.0,
                        correlation_factor=1.0,
                        governance_hard_cap=0.10) -> DynamicRiskBudget:
    """动态风险预算。

    参数：
        base_budget          基础预算（如单股 10%）
        permission           BLOCK/WATCH/TEST/ALLOW/STRONG_ALLOW
        wave_quality         STRONG/MEDIUM/WEAK/NONE
        regime               市场状态
        portfolio_state      组合状态
        volatility_factor    波动缩放（>1 = 波动高 → 降预算）
        liquidity_factor     流动性缩放（<1 = 流动性差 → 降预算）
        correlation_factor   相关性缩放（>1 = 高相关 → 降预算）
        governance_hard_cap  治理硬上限（不可突破）
    """
    pf = _factor(PERMISSION_FACTOR, permission)
    wf = _factor(WAVE_FACTOR, wave_quality)
    rf = _factor(REGIME_FACTOR, regime)
    pof = _factor(PORTFOLIO_FACTOR, portfolio_state)
    vf = max(0.1, float(volatility_factor or 1.0))
    lf = max(0.1, float(liquidity_factor or 1.0))
    cf = max(0.1, float(correlation_factor or 1.0))
    factors = {"permission": pf, "wave": wf, "regime": rf,
               "portfolio": pof, "volatility": round(1.0 / vf, 4),
               "liquidity": round(1.0 / lf, 4),
               "correlation": round(1.0 / cf, 4)}
    dynamic = (float(base_budget) * pf * wf * rf * pof
               * (1.0 / vf) * (1.0 / lf) * (1.0 / cf))
    hard_cap = float(governance_hard_cap or 0.10)
    capped = dynamic > hard_cap
    final = min(dynamic, hard_cap)
    reasons = []
    if permission in ("BLOCK", "WATCH"):
        reasons.append(f"PERMISSION_FACTOR_{permission}={pf}")
    if wave_quality in ("WEAK", "NONE"):
        reasons.append(f"WAVE_FACTOR_{wave_quality}={wf}")
    if regime in ("Bear", "Crisis"):
        reasons.append(f"REGIME_FACTOR_{regime}={rf}")
    if portfolio_state in ("RISK_OFF", "OVERHEATED", "CONCENTRATED"):
        reasons.append(f"PORTFOLIO_FACTOR_{portfolio_state}={pof}")
    if capped:
        reasons.append(f"GOVERNANCE_HARD_CAP({hard_cap:.0%})")
    return DynamicRiskBudget(
        base_budget=round(float(base_budget), 4), factors=factors,
        dynamic_budget=round(dynamic, 4), hard_cap=round(hard_cap, 4),
        final_budget=round(final, 4), capped=capped,
        reasons=tuple(reasons))
