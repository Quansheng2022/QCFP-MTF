# coding: utf-8
"""Tail-Risk / Gap-Risk Engine（QCFP-MTF 2.8：78 号尾部与跳空风险）

普通 Risk 模型假设价格连续调整，但真实市场可能 Close=100 → Next Open=85：
    Stop=95 并不能保证在 95 卖出。

计算：
    Gap Risk / Tail Risk / Liquidity Collapse / Trading Halt /
    Event Risk → Worst Expected Loss

仓位应基于 Tail Risk 而非仅 Normal Risk。
"""

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class TailGapRisk:
    normal_risk: float
    gap_risk: float
    tail_risk: float
    worst_expected_loss: float
    tail_position_scale: float
    reasons: tuple = field(default_factory=tuple)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["reasons"] = list(self.reasons)
        return d


def tail_gap_risk(weekly_vol, gap_p95=None, gap_p99=None,
                  liquidity_collapse_pct=0.0, trading_halt=False,
                  event_risk=0.0) -> TailGapRisk:
    """尾部/跳空风险。

    输入：
        weekly_vol            周波动率（Normal Risk 基准）
        gap_p95 / gap_p99      跳空分布分位（close→open 绝对跌幅）
        liquidity_collapse_pct 流动性崩塌额外损失（0-1）
        trading_halt           停牌标记（无法止损）
        event_risk             事件风险额外损失（0-1）
    """
    reasons = []
    normal = abs(float(weekly_vol or 0.0))
    gap = abs(float(gap_p99 if gap_p99 is not None else gap_p95 or 0.0))
    # Tail Risk = 正常波动 + 跳空 + 流动性崩塌 + 停牌/事件溢价
    halt_premium = 0.03 if trading_halt else 0.0
    tail = normal + gap + float(liquidity_collapse_pct or 0.0) \
        + halt_premium + float(event_risk or 0.0)
    worst = normal + max(gap, tail * 0.5) + float(liquidity_collapse_pct
                                                   or 0.0) + halt_premium
    if gap > 0:
        reasons.append(f"GAP_RISK({gap:.1%})")
    if trading_halt:
        reasons.append("TRADING_HALT_STOP_UNRELIABLE")
    if float(liquidity_collapse_pct or 0.0) > 0:
        reasons.append("LIQUIDITY_COLLAPSE")
    # 仓位缩放：Tail Risk 越高 → 可承担仓位越小
    scale = min(1.0, normal / max(tail, 1e-9)) if tail > 0 else 1.0
    return TailGapRisk(
        normal_risk=round(normal, 4), gap_risk=round(gap, 4),
        tail_risk=round(tail, 4),
        worst_expected_loss=round(worst, 4),
        tail_position_scale=round(scale, 4),
        reasons=tuple(reasons))


def tail_adjusted_position(target, weekly_vol, **tail_kw) -> dict:
    """按 Tail Risk 调整目标仓位（不只按 Normal Risk）。"""
    r = tail_gap_risk(weekly_vol, **tail_kw)
    t = float(target or 0.0)
    return {"original_target": round(t, 4),
            "tail_position_scale": r.tail_position_scale,
            "adjusted_target": round(t * r.tail_position_scale, 4),
            "risk": r.as_dict()}
