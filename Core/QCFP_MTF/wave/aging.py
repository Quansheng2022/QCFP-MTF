# coding: utf-8
"""Opportunity Aging Engine（QCFP-MTF 2.8：42 号波段机会衰减引擎）

回答"一个好机会是不是已经太晚"：
    Wave Discovery → Early → Expansion → Mature → Late → Expired

计算：
    Opportunity Age / Expected Remaining MFE / Realized MFE / MFE Decay /
    Time Since Confirmation

规则：Wave STRONG 但已实现 ≥90% 预期 MFE → 不再允许 Full Entry
    （entry_allowed=False，或只允许观察仓）。
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime


AGING_STAGES = ("EARLY", "EXPANSION", "MATURE", "LATE", "EXPIRED")


@dataclass(frozen=True)
class OpportunityAging:
    wave_id: str
    stock_code: str
    opportunity_age_days: int
    expected_mfe: float
    realized_mfe: float
    mfe_decay: float            # 已实现占预期比例（0-1+）
    expected_remaining_mfe: float
    time_since_confirmation_days: int
    stage: str
    entry_allowed: bool
    max_entry_scale: float      # 允许的最大进场仓位比例
    reasons: tuple = field(default_factory=tuple)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["reasons"] = list(self.reasons)
        return d


def _days(start, end):
    try:
        d1 = datetime.strptime(str(start)[:10], "%Y-%m-%d")
        d2 = datetime.strptime(str(end)[:10], "%Y-%m-%d")
        return max(0, (d2 - d1).days)
    except Exception:
        return 0


def _stage(decay, age, max_age=120, late_decay=0.75,
           mature_decay=0.5, expansion_decay=0.25) -> str:
    if age > max_age:
        return "EXPIRED"
    if decay >= 0.9:
        return "LATE" if decay < 1.0 else "EXPIRED"
    if decay >= late_decay:
        return "LATE"
    if decay >= mature_decay:
        return "MATURE"
    if decay >= expansion_decay:
        return "EXPANSION"
    return "EARLY"


def evaluate_opportunity_aging(wave_id, stock_code, discovered_at, as_of,
                               expected_mfe, realized_mfe,
                               confirmed_at=None,
                               max_age_days=120,
                               late_threshold=0.90,
                               min_remaining_for_full=0.15) \
        -> OpportunityAging:
    """机会衰减评估。

    late_threshold：已实现 ≥ 该比例 → 不再允许 Full Entry。
    min_remaining_for_full：剩余预期 MFE ≥ 该比例才允许满仓。
    """
    age = _days(discovered_at, as_of)
    since_confirm = _days(confirmed_at or discovered_at, as_of)
    exp = float(expected_mfe or 0.0)
    realized = float(realized_mfe or 0.0)
    decay = realized / exp if exp > 0 else 0.0
    remaining = max(0.0, exp - realized)
    stage = _stage(decay, age, max_age=max_age_days)
    reasons = []
    if stage in ("LATE", "EXPIRED"):
        reasons.append(f"OPPORTUNITY_{stage}(decay={decay:.0%})")
    if decay >= late_threshold:
        reasons.append(f"MFE_LARGELY_REALIZED({decay:.0%}>={late_threshold:.0%})")
    remaining_ratio = remaining / exp if exp > 0 else 0.0
    if remaining_ratio < min_remaining_for_full:
        reasons.append(f"REMAINING_MFE_TOO_LOW({remaining_ratio:.0%})")
    entry_allowed = stage not in ("LATE", "EXPIRED") \
        and decay < late_threshold
    # 允许的最大进场比例：越晚越小（MATURE→0.5，EXPANSION→1.0，LATE→0）
    max_scale = {"EARLY": 1.0, "EXPANSION": 1.0, "MATURE": 0.5,
                 "LATE": 0.0, "EXPIRED": 0.0}.get(stage, 0.0)
    if remaining_ratio < min_remaining_for_full:
        max_scale = min(max_scale, 0.0 if decay >= late_threshold else 0.25)
    return OpportunityAging(
        wave_id=wave_id, stock_code=stock_code,
        opportunity_age_days=age,
        expected_mfe=round(exp, 4), realized_mfe=round(realized, 4),
        mfe_decay=round(decay, 4),
        expected_remaining_mfe=round(remaining, 4),
        time_since_confirmation_days=since_confirm,
        stage=stage, entry_allowed=entry_allowed,
        max_entry_scale=round(max_scale, 4),
        reasons=tuple(reasons))


def opportunity_decay(age_days, half_life_days=5.0,
                      momentum=0.0, volatility=0.2,
                      liquidity_score=1.0, regime_scale=1.0,
                      stage_multiplier=None) -> dict:
    """机会价值时间衰减（62 号）：
        Opportunity Value(t) = 100% × (0.5)^(t / half_life) × factor

    half_life 由环境因子调制：
        动量↑ → 衰减更慢；波动↑ → 衰减更快；流动性差 → 衰减更快；
        Regime 差 → 衰减更快；Wave 阶段（MATURE/LATE）→ 衰减更快。
    """
    stage_mult = stage_multiplier or {
        "DISCOVERY": 1.0, "CONFIRMING": 1.0, "ACTIVE": 1.0,
        "MATURE": 0.7, "EXHAUSTING": 0.4, "INVALID": 0.0}
    mom = max(-1.0, min(1.0, float(momentum or 0.0)))
    vol = max(0.01, float(volatility or 0.2))
    liq = max(0.1, float(liquidity_score or 1.0))
    reg = max(0.1, float(regime_scale or 1.0))
    factor = (1.0 + 0.5 * mom) * (1.0 - 0.3 * min(1.0, (vol - 0.15) / 0.15))
    factor *= (0.7 + 0.3 * liq)
    factor *= reg
    eff_half_life = max(0.5, float(half_life_days) * factor)
    t = max(0, int(age_days or 0))
    value = 100.0 * (0.5 ** (t / eff_half_life))
    return {
        "age_days": t,
        "half_life_days": round(eff_half_life, 2),
        "opportunity_value_pct": round(value, 2),
        "remaining_ratio": round(value / 100.0, 4),
        "factors": {"momentum": round(mom, 3),
                    "volatility": round(vol, 3),
                    "liquidity": round(liq, 3),
                    "regime_scale": round(reg, 3)},
    }
