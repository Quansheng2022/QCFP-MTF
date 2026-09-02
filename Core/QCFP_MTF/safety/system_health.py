# coding: utf-8
"""System Health / Incident / Kill-Switch（QCFP-MTF 2.8：20 号）

统一 7 维健康度（Data/Feature/Decision/Risk/Execution/Ledger/Research）
→ GREEN / YELLOW / ORANGE / RED / HALT，并与 Model Doubt Index 合并：

    Continuous Monitoring → Data/Model/Execution Drift → Model Doubt →
    Risk Adjustment → NORMAL/DEFENSIVE/SAFE_MODE → HALT
"""

from dataclasses import asdict, dataclass, field


HEALTH_DIMENSIONS = ("data", "feature", "decision", "risk", "execution",
                     "ledger", "research")


@dataclass(frozen=True)
class SystemHealth:
    dimensions: dict
    status: str          # GREEN / YELLOW / ORANGE / RED / HALT
    incidents: tuple
    kill_switch: bool

    def as_dict(self) -> dict:
        d = asdict(self)
        d["incidents"] = list(self.incidents)
        return d


def system_health(checks: dict, mdi_score=0.0) -> SystemHealth:
    """系统健康度。

    checks：{data: 0-100, feature: ..., decision: ..., risk: ...,
             execution: ..., ledger: ..., research: ...}
    mdi_score：Model Doubt Index（0-100，越高越怀疑）。
    """
    dimensions = {}
    incidents = []
    worst = 100.0
    for dim in HEALTH_DIMENSIONS:
        s = float(checks.get(dim, 100.0))
        dimensions[dim] = round(s, 1)
        worst = min(worst, s)
        if s < 60:
            incidents.append(f"{dim}:{s:.0f}")
    # 合并 Model Doubt
    mdi = float(mdi_score or 0.0)
    if mdi >= 80:
        incidents.append(f"MODEL_DOUBT:{mdi:.0f}")
        worst = min(worst, 0.0)
    elif mdi >= 40:
        worst = min(worst, 60.0)
    if worst >= 90:
        status = "GREEN"
    elif worst >= 75:
        status = "YELLOW"
    elif worst >= 60:
        status = "ORANGE"
    elif worst > 0:
        status = "RED"
    else:
        status = "HALT"
    kill = status == "HALT" or "ledger" in incidents \
        or "decision" in incidents
    return SystemHealth(dimensions=dimensions, status=status,
                        incidents=tuple(incidents), kill_switch=kill)
