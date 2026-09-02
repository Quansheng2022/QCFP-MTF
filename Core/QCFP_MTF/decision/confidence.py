# coding: utf-8
"""Decision Confidence / Evidence Score（QCFP-MTF 2.7）

Evidence → Confidence → Decision Strength。
Confidence **不能突破 Permission，也不能直接决定仓位**；
它只影响"是否等待确认 / 建仓速度 / 加仓力度 / 信号优先级"的展示与节奏。
"""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class DecisionConfidence:
    institutional_evidence: float
    wave_evidence: float
    risk_evidence: float
    data_quality: str
    pit_quality: str
    score: float
    band: str

    def as_dict(self) -> dict:
        return asdict(self)


def _band(score: float) -> str:
    return "High" if score >= 60 else "Medium" if score >= 35 else "Low"


def evaluate_confidence(institutional_state=None, institutional_permission=None,
                        setup_type=None, risk_level=None,
                        data_quality="B", pit_grade="C",
                        exit_severity=0) -> DecisionConfidence:
    """Evidence Score（0-100）：机构/波段/风险/数据/PIT 五维加权"""
    # 机构证据（25）
    inst = 0.0
    if institutional_state in ("ACCUMULATION", "ACCUMULATION_WEAK"):
        inst = 18 if institutional_permission in ("ALLOW", "STRONG_ALLOW") \
            else 8
    elif institutional_state in ("RECOVERY",):
        inst = 14 if institutional_permission in ("TEST", "ALLOW") else 6
    elif institutional_state in ("NEUTRAL",):
        inst = 6
    else:  # DISTRIBUTION/CAPITULATION
        inst = 0
    # 波段证据（25）
    wave = {"BREAKOUT": 25, "PULLBACK": 22, "RECOVERY": 18,
            "ACCUMULATION": 14, "NONE": 0, None: 0}.get(setup_type, 0)
    # 风险证据（20）
    risk = {"Low": 20, "Medium": 12, "High": 3, "Extreme": 0}.get(
        risk_level, 8)
    # 数据质量（15）
    dq = {"A": 15, "B": 12, "C": 6, "D": 0}.get(data_quality, 6)
    # PIT 质量（15）
    pit = {"A": 15, "B": 12, "C": 6, "D": 0}.get(pit_grade, 6)
    score = inst + wave + risk + dq + pit
    if exit_severity >= 3:
        score = 0.0
    score = max(0.0, min(100.0, score))
    return DecisionConfidence(
        institutional_evidence=round(inst, 1),
        wave_evidence=round(wave, 1),
        risk_evidence=round(risk, 1),
        data_quality=data_quality or "B",
        pit_quality=pit_grade or "C",
        score=round(score, 2), band=_band(score))


def confidence_position_multiplier(score, permission="ALLOW",
                                   governance_cap=1.0) -> dict:
    """置信度 → 仓位乘数（57 号）。

    score > 0.85 → 100%
    0.70–0.85   → 70%
    0.55–0.70   → 40%
    < 0.55      → TEST / WATCH（观察仓）

    硬约束：Confidence 不能绕过 Risk/Permission——
        multiplier ≤ governance_cap，且 BLOCK/WATCH 权限下不放大。
    """
    s = float(score or 0.0)
    if s > 0.85:
        mult, band = 1.0, "HIGH"
    elif s >= 0.70:
        mult, band = 0.7, "MEDIUM_HIGH"
    elif s >= 0.55:
        mult, band = 0.4, "MEDIUM"
    else:
        mult, band = 0.1, "LOW"
    # 治理钳制：BLOCK→0；WATCH→观察上限；Confidence ≤ Governance Cap
    if permission == "BLOCK":
        mult = 0.0
    elif permission == "WATCH":
        mult = min(mult, 0.2)
    mult = min(mult, float(governance_cap))
    return {"score": round(s, 4), "band": band,
            "position_multiplier": round(mult, 4),
            "governance_capped": mult < (1.0 if s > 0.85 else
                                         0.7 if s >= 0.70 else
                                         0.4 if s >= 0.55 else 0.1)}
