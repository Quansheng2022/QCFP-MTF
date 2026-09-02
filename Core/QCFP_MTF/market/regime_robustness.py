# coding: utf-8
"""Regime Robustness / Transition（QCFP-MTF 2.8：38 号环境适应能力）

五类 Regime：Institutional / Market / Volatility / Liquidity / Trend
状态：REGIME_STABLE / REGIME_TRANSITION / REGIME_UNCERTAIN

核心：真正危险的不是"已知是 Bear"，而是"正在从 Bull→Bear"。
    REGIME_TRANSITION → Permission 自动收紧（风险预算 ↓）
"""

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class RegimeState:
    name: str
    state: str                 # REGIME_STABLE / REGIME_TRANSITION / REGIME_UNCERTAIN
    transition_probability: float
    permission_scale: float
    reasons: tuple = field(default_factory=tuple)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["reasons"] = list(self.reasons)
        return d


def regime_state(name, transition_probability, unstable_regimes=("Bear",),
                 warn_prob=0.3, uncertain_prob=0.5) -> RegimeState:
    """单一 Regime 状态判定。

    transition_probability 高 → TRANSITION；
    处于不稳定 regime 且概率中 → UNCERTAIN；
    否则 STABLE。
    """
    p = float(transition_probability or 0.0)
    if p >= uncertain_prob:
        state, scale, reasons = "REGIME_TRANSITION", 0.5, \
            [f"TRANSITION_PROBABILITY_HIGH({p:.0%})"]
    elif p >= warn_prob:
        if name in unstable_regimes:
            state, scale, reasons = "REGIME_UNCERTAIN", 0.7, \
                [f"UNSTABLE_{name}({p:.0%})"]
        else:
            state, scale, reasons = "REGIME_TRANSITION", 0.8, \
                [f"TRANSITION_WATCH({p:.0%})"]
    else:
        state, scale, reasons = "REGIME_STABLE", 1.0, \
            [f"STABLE_{name}"]
    return RegimeState(name=name, state=state,
                       transition_probability=round(p, 4),
                       permission_scale=round(scale, 4),
                       reasons=tuple(reasons))


def regime_robustness_report(regimes: dict) -> dict:
    """五类 Regime 汇总：整体收紧 = min(各 permission_scale)。"""
    states = {name: regime_state(name, prob).as_dict()
              for name, prob in regimes.items()}
    scales = [s["permission_scale"] for s in states.values()]
    overall_scale = min(scales) if scales else 1.0
    transitions = [n for n, s in states.items()
                   if s["state"] == "REGIME_TRANSITION"]
    uncertain = [n for n, s in states.items()
                 if s["state"] == "REGIME_UNCERTAIN"]
    return {
        "regimes": states,
        "overall_permission_scale": round(overall_scale, 4),
        "transition_regimes": transitions,
        "uncertain_regimes": uncertain,
        "tightened": overall_scale < 1.0,
    }
