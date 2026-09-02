# coding: utf-8
"""Strategy Ensemble / Module Consensus（QCFP-MTF 2.8：58 号模块共识）

不要让单一模块成为唯一 Alpha 来源：
    Wave / Trend / Momentum / Liquidity / FSM 各自投票（+1/0/-1）
    → Consensus = 加权和 → HIGH / MEDIUM / LOW

Wave=STRONG 但 Trend/Liquidity 为负 → Consensus=LOW → 自动 Reduce
（不能仅因 Wave 很强就继续做）。
"""

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class ModuleConsensus:
    votes: dict
    weighted_score: float
    band: str              # HIGH / MEDIUM / LOW
    recommend_reduce: bool
    reasons: tuple = field(default_factory=tuple)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["reasons"] = list(self.reasons)
        return d


def module_consensus(votes: dict, weights: dict = None) -> ModuleConsensus:
    """votes：{module: +1/0/-1}。
    weights 默认：wave 0.30 / trend 0.20 / momentum 0.15 /
                liquidity 0.20 / fsm 0.15。
    """
    w = weights or {"wave": 0.30, "trend": 0.20, "momentum": 0.15,
                    "liquidity": 0.20, "fsm": 0.15}
    score = sum(float(votes.get(m, 0.0)) * float(w.get(m, 0.0))
                for m in w)
    if score >= 0.4:
        band = "HIGH"
    elif score >= 0.0:
        band = "MEDIUM"
    else:
        band = "LOW"
    reasons = []
    if float(votes.get("wave", 0.0)) > 0 and score < 0.0:
        reasons.append("WAVE_STRONG_BUT_CONSENSUS_LOW")
    if float(votes.get("trend", 0.0)) < 0:
        reasons.append("TREND_NEGATIVE")
    if float(votes.get("liquidity", 0.0)) < 0:
        reasons.append("LIQUIDITY_NEGATIVE")
    return ModuleConsensus(
        votes=dict(votes),
        weighted_score=round(score, 4), band=band,
        recommend_reduce=band == "LOW",
        reasons=tuple(reasons))
