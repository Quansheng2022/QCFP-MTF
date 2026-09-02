# coding: utf-8
"""Position Scaling Policy（QCFP-MTF 2.8：76 号动态仓位扩缩策略）

仓位在交易生命周期内随机会质量动态变化：
    Wave Confirmed → 2% → Entry Confirmed → 3% → Breakout → 5% →
    Wave Maturity → 4% → Decay → 2% → Exit

原则：
    Signal↑ / Risk↓ → Position↑
    Signal↓ / Risk↑ → Position↓
硬约束：Final ≤ Permission ≤ Risk ≤ Portfolio ≤ Liquidity
（动态加仓不是突破治理边界，而是在边界内部优化资金使用）。
"""

from dataclasses import asdict, dataclass, field


SCALING_TABLE = {
    "DISCOVERY": 0.0, "CONFIRMING": 0.02, "ACTIVE": 0.03,
    "MATURE": 0.05, "EXHAUSTING": 0.02, "INVALID": 0.0,
}


@dataclass(frozen=True)
class ScalingResult:
    stage: str
    raw_scale: float
    final_position: float
    caps: dict
    capped: bool
    reasons: tuple = field(default_factory=tuple)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["reasons"] = list(self.reasons)
        return d


def position_scaling_policy(stage, current_position=0.0,
                            signal_trend=1.0, risk_trend=1.0,
                            permission_cap=0.20, risk_cap=0.15,
                            portfolio_cap=0.10, liquidity_cap=0.08,
                            scale_table=None) -> ScalingResult:
    """动态仓位扩缩。

    signal_trend > 1 = 信号增强；risk_trend > 1 = 风险上升。
    目标 = 阶段基准 × signal/risk 调制，再 min 各治理 cap。
    """
    table = scale_table or SCALING_TABLE
    base = float(table.get(stage, 0.0))
    signal = float(signal_trend or 1.0)
    risk = float(risk_trend or 1.0)
    modulated = base * max(0.0, signal) / max(0.1, risk)
    caps = {"permission": float(permission_cap or 1.0),
            "risk": float(risk_cap or 1.0),
            "portfolio": float(portfolio_cap or 1.0),
            "liquidity": float(liquidity_cap or 1.0)}
    final = min(modulated, min(caps.values()))
    capped = final < modulated - 1e-9
    reasons = []
    if signal > 1.0 and risk < 1.0:
        reasons.append("SIGNAL_UP_RISK_DOWN_EXPAND")
    if signal < 1.0 or risk > 1.0:
        reasons.append("CONTRACT")
    if capped:
        reasons.append("GOVERNANCE_CAP_BOUND")
    return ScalingResult(
        stage=stage, raw_scale=round(modulated, 4),
        final_position=round(final, 4), caps=caps,
        capped=capped, reasons=tuple(reasons))
