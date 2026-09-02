# coding: utf-8
"""Strategy Capacity Allocation（QCFP-MTF 2.8：88 号策略容量分配）

多个 Alpha 策略之间分配有限风险预算：
    Wave / Breakout / Entry / Mean Reversion / Event ...

动态考虑：Recent Performance / Correlation / Capacity / Drawdown /
           Regime / Confidence / Cost
约束层级：Governance > Portfolio Risk > Strategy Allocation > Signal
（不能因某策略近期表现好就突破 Portfolio Risk）。
"""

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class StrategyAllocation:
    allocations: dict
    total_risk_budget: float
    governance_capped: bool
    reasons: tuple = field(default_factory=tuple)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["reasons"] = list(self.reasons)
        return d


def strategy_allocation(strategies, total_risk_budget=0.10,
                        portfolio_risk_cap=0.10,
                        max_per_strategy=0.05,
                        min_allocation=0.005) -> StrategyAllocation:
    """策略容量分配。

    strategies：{name: {"score": 0-1, "capacity": 0-1, "drawdown": 0-1,
                        "correlation": 0-1, "confidence": 0-1,
                        "cost": 0-1}}
    分配 = budget × (score×0.3 + confidence×0.2 + capacity×0.2 +
                    (1-drawdown)×0.15 + (1-cost)×0.15) / Σ
    并受 max_per_strategy 与 portfolio_risk_cap 钳制。
    """
    if not strategies:
        return StrategyAllocation({}, float(total_risk_budget), False, ())
    scores = {}
    for name, s in strategies.items():
        score = (float(s.get("score") or 0.0) * 0.3
                 + float(s.get("confidence") or 0.0) * 0.2
                 + float(s.get("capacity") or 0.0) * 0.2
                 + (1.0 - float(s.get("drawdown") or 0.0)) * 0.15
                 + (1.0 - float(s.get("cost") or 0.0)) * 0.15)
        scores[name] = max(0.0, score)
    total = sum(scores.values()) or 1.0
    budget = float(total_risk_budget)
    cap = min(float(portfolio_risk_cap), float(max_per_strategy))
    allocations = {}
    used = 0.0
    for name, s in sorted(scores.items(), key=lambda x: -x[1]):
        alloc = budget * s / total
        alloc = min(alloc, cap)
        room = budget - used
        if alloc > room:
            alloc = room
        if alloc < float(min_allocation):
            allocations[name] = 0.0
            continue
        allocations[name] = round(alloc, 4)
        used += alloc
    governed = bool(cap < budget)
    return StrategyAllocation(
        allocations=allocations, total_risk_budget=round(budget, 4),
        governance_capped=governed,
        reasons=("GOVERNANCE_CAP" if governed else "BUDGET_ALLOCATED",))
