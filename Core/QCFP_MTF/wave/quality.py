# coding: utf-8
"""Wave Quality Decomposition（QCFP-MTF 2.8：73 号 Wave 质量分解）

Wave 不再只有一个总分，而是分解为：
    Strength / Persistence / Acceleration / Maturity /
    Remaining Opportunity / Confirmation / Failure Risk

两个 Wave Score=85 的股票可能完全不同：
    A：Strength 90 + Maturity 30 + Remaining 90（早期强机会）
    B：Strength 95 + Maturity 90 + Remaining 35（已成熟）
"""

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class WaveQuality:
    strength: float
    persistence: float
    acceleration: float
    maturity: float
    remaining_opportunity: float
    confirmation: float
    failure_risk: float
    composite: float

    def as_dict(self) -> dict:
        return asdict(self)


def _clamp(v):
    return max(0.0, min(100.0, float(v or 0.0)))


def wave_quality_decomposition(strength=0.0, persistence=0.0,
                               acceleration=0.0, maturity=0.0,
                               remaining_opportunity=0.0,
                               confirmation=0.0, failure_risk=0.0) \
        -> WaveQuality:
    """Wave 质量分解（各分量 0-100）。

    composite = 0.25×Strength + 0.20×(100−Maturity) + 0.20×Remaining +
                0.15×Persistence + 0.10×Acceleration + 0.10×Confirmation
                − 0.15×FailureRisk（clamp 到 0-100）。
    """
    s = _clamp(strength)
    p = _clamp(persistence)
    a = _clamp(acceleration)
    m = _clamp(maturity)
    rem = _clamp(remaining_opportunity)
    c = _clamp(confirmation)
    f = _clamp(failure_risk)
    composite = (0.25 * s + 0.20 * (100 - m) + 0.20 * rem
                 + 0.15 * p + 0.10 * a + 0.10 * c - 0.15 * f)
    return WaveQuality(
        strength=round(s, 2), persistence=round(p, 2),
        acceleration=round(a, 2), maturity=round(m, 2),
        remaining_opportunity=round(rem, 2),
        confirmation=round(c, 2), failure_risk=round(f, 2),
        composite=round(max(0.0, min(100.0, composite)), 2))
