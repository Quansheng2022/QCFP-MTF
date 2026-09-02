# coding: utf-8
"""Liquidity-aware Exit（QCFP-MTF 2.8：流动性感知退出）

把"理论上的减仓/清仓"变成"可执行的退出计划"：
    Position Size → ADV → Participation Rate → Exit Days
    → Slippage → Stress Cost → LIQUIDITY_LOW + EXIT_REQUIRED
    → DELEVERAGE_PLAN（每日可卖金额 + 天数 + 总成本）

判定：
    exit_days <= 1 且 impact < 0.5% → LIQUIDITY_OK
    exit_days <= 3 且 impact < 1.0% → LIQUIDITY_FAIR
    否则                          → LIQUIDITY_LOW
    EXIT_REQUIRED（硬退出/治理强制）+ LIQUIDITY_LOW
    → DELEVERAGE_PLAN（分批退出计划）

2.8 增量：流动性恶化应主动压缩 Target——
    LIQUIDITY_OK → ×1.0 / FAIR → ×0.7 / LOW → ×0.4 /
    LOW + EXIT_REQUIRED → ×0.0
"""

from dataclasses import asdict, dataclass, field
from datetime import date, timedelta

from .capacity import exit_stress_days, market_impact, participation_rate


@dataclass(frozen=True)
class LiquidityExitAssessment:
    position_value: float
    adv: float
    participation: float
    exit_days: int
    impact: float
    slippage_bps: float
    stress_cost_bps: float
    liquidity_flag: str        # LIQUIDITY_OK / LIQUIDITY_FAIR / LIQUIDITY_LOW
    exit_required: bool
    deleverage_plan: dict = field(default_factory=dict)
    reasons: tuple = field(default_factory=tuple)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["reasons"] = list(self.reasons)
        return d


def _flag(exit_days, impact) -> str:
    if exit_days <= 1 and impact < 0.005:
        return "LIQUIDITY_OK"
    if exit_days <= 3 and impact < 0.01:
        return "LIQUIDITY_FAIR"
    return "LIQUIDITY_LOW"


def build_deleverage_plan(position_value, adv, participation,
                          start_date, exit_days, holidays=None,
                          half_day_dates=None, suspended_dates=None) -> dict:
    """分批退出计划（12 号：交易日模型）。

    每日上限 = ADV × participation；**只用实际可交易日推进**
    （跳过周末/交易所休市日/半日市容量减半/停牌日不可卖）。
    cumulative_pct 为真正累计值。
    """
    def _is_trading_day(d, holidays):
        return d.weekday() < 5 and d.isoformat() not in holidays
    daily_cap = max(0.0, float(adv) * float(participation))
    if daily_cap <= 0:
        return {"daily_cap": 0.0, "days": 0, "slices": [],
                "end_date": "", "note": "ADV 无效，无法形成退出计划"}
    remaining = float(position_value)
    slices = []
    try:
        cur = date.fromisoformat(str(start_date)[:10])
    except ValueError:
        cur = date.today()
    holidays = set(holidays or ())
    half_days = set(half_day_dates or ())
    suspended = set(suspended_dates or ())
    guard = 0
    while remaining > 1e-6 and len(slices) < 10:
        guard += 1
        if not _is_trading_day(cur, holidays) \
                or cur.isoformat() in suspended:
            cur += timedelta(days=1)
            if guard > 60:
                break
            continue
        day_cap = daily_cap * (0.5 if cur.isoformat() in half_days else 1.0)
        amount = min(day_cap, remaining)
        slices.append({"date": cur.isoformat(),
                       "amount": round(amount, 2),
                       "cumulative_pct": round(
                           (float(position_value) - remaining + amount)
                           / float(position_value), 4)})
        remaining -= amount
        cur += timedelta(days=1)
    return {
        "daily_cap": round(daily_cap, 2),
        "days": len(slices),
        "slices": slices,
        "end_date": slices[-1]["date"] if slices else "",
        "note": "分批退出计划（仅实际可交易日，跳过休市/停牌）",
    }


def evaluate_liquidity_exit(position_value, adv, participation=0.10,
                            exit_required=False, slippage_bps=10.0,
                            stress_cost_bps=20.0, start_date="",
                            max_impact=0.01, max_stress_days=3) \
        -> LiquidityExitAssessment:
    """流动性感知退出评估。"""
    pv = float(position_value or 0.0)
    adv = float(adv or 0.0)
    if pv <= 0:
        return LiquidityExitAssessment(
            position_value=0.0, adv=adv, participation=float(participation),
            exit_days=0, impact=0.0, slippage_bps=float(slippage_bps),
            stress_cost_bps=float(stress_cost_bps), liquidity_flag="LIQUIDITY_OK",
            exit_required=False, deleverage_plan={},
            reasons=("NO_POSITION",))
    days = exit_stress_days(pv, adv, participation) or 999
    impact = market_impact(pv, adv, participation)
    pr = participation_rate(pv, adv)
    flag = _flag(days, impact)
    reasons = []
    if flag == "LIQUIDITY_LOW":
        reasons.append(f"EXIT_DAYS={days}>={max_stress_days}")
        if impact > max_impact:
            reasons.append(f"IMPACT={impact:.4f}>{max_impact:.2f}")
    if exit_required and flag == "LIQUIDITY_LOW":
        reasons.append("DELEVERAGE_PLAN_REQUIRED")
    plan = {}
    if exit_required and flag == "LIQUIDITY_LOW" and adv > 0:
        plan = build_deleverage_plan(pv, adv, participation, start_date, days)
    total_cost = float(slippage_bps + stress_cost_bps) / 10000.0
    return LiquidityExitAssessment(
        position_value=round(pv, 2), adv=round(adv, 2),
        participation=float(participation), exit_days=int(days),
        impact=round(impact, 6),
        slippage_bps=float(slippage_bps),
        stress_cost_bps=float(stress_cost_bps),
        liquidity_flag=flag, exit_required=bool(exit_required),
        deleverage_plan=plan, reasons=tuple(reasons))


def liquidity_target_scale(assessment: LiquidityExitAssessment,
                           target=None) -> dict:
    """流动性恶化 → 主动压缩目标仓位。

    返回 {target_scale, compressed_target(可选), reason}。
    """
    flag = assessment.liquidity_flag
    if assessment.exit_required and flag == "LIQUIDITY_LOW":
        scale, reason = 0.0, "LIQUIDITY_EXIT_REQUIRED"
    elif flag == "LIQUIDITY_OK":
        scale, reason = 1.0, "LIQUIDITY_OK"
    elif flag == "LIQUIDITY_FAIR":
        scale, reason = 0.7, "LIQUIDITY_FAIR"
    else:
        scale, reason = 0.4, "LIQUIDITY_LOW"
    out = {"target_scale": scale, "reason": reason}
    if target is not None:
        out["compressed_target"] = round(float(target) * scale, 4)
    return out
