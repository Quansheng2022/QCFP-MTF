# coding: utf-8
"""Market Opportunity Regime（QCFP-MTF 2.8：71 号市场机会环境分层）

"允许做" ≠ "现在值得积极做"：
    REGIME_0 防御 / REGIME_1 低机会 / REGIME_2 正常 /
    REGIME_3 高机会 / REGIME_4 极强机会

    Market Regime → Permission → Wave → Capital Aggression
避免在"允许交易但整体机会质量很差"的市场里过度交易。
"""

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class OpportunityRegime:
    level: int                 # 0-4
    label: str                 # 防御/低机会/正常/高机会/极强机会
    capital_aggression: float  # 0-1 组合进攻系数
    reasons: tuple = field(default_factory=tuple)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["reasons"] = list(self.reasons)
        return d


def market_opportunity_regime(opportunity_share=0.5, wave_hit_rate=0.5,
                              breadth=0.5, permission_strength=0.5,
                              risk_off=False) -> OpportunityRegime:
    """市场机会环境判定。

    输入（均 0-1）：
        opportunity_share   高机会股票占比
        wave_hit_rate       Wave 历史胜率/命中率
        breadth             市场广度（上涨股票占比）
        permission_strength 平均机构权限强度
        risk_off            风险关闭标记
    """
    reasons = []
    if risk_off:
        return OpportunityRegime(0, "防御", 0.0, ("RISK_OFF",))
    score = (float(opportunity_share) * 0.30 + float(wave_hit_rate) * 0.25
             + float(breadth) * 0.25 + float(permission_strength) * 0.20)
    if score >= 0.8:
        level, label, aggression = 4, "极强机会", 1.0
    elif score >= 0.65:
        level, label, aggression = 3, "高机会", 0.8
    elif score >= 0.45:
        level, label, aggression = 2, "正常", 0.6
    elif score >= 0.25:
        level, label, aggression = 1, "低机会", 0.3
    else:
        level, label, aggression = 0, "防御", 0.1
    reasons.append(f"OPPORTUNITY_SCORE({score:.2f})")
    return OpportunityRegime(level, label, aggression, tuple(reasons))
