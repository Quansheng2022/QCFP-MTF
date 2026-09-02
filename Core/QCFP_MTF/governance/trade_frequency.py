# coding: utf-8
"""Trade Frequency Governor（QCFP-MTF 2.8：67 号交易频率治理器）

防止"不断交易追逐噪音"：
    Daily Trade Limit / Weekly Turnover Limit / Portfolio Turnover Budget /
    Per-Symbol Cooldown

当 Signal Frequency↑ / Turnover↑ / Edge↓ → 主动收紧 Trade Threshold
甚至 WATCH / HOLD。
"""

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class FrequencyGate:
    allowed: bool
    mode: str               # NORMAL / TIGHTENED / WATCH / HOLD
    threshold_scale: float  # >1 = 进场门槛上调
    reasons: tuple = field(default_factory=tuple)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["reasons"] = list(self.reasons)
        return d


def trade_frequency_gate(daily_trades, daily_limit=5,
                         weekly_turnover=1.0, weekly_turnover_limit=2.0,
                         portfolio_turnover=0.0,
                         portfolio_turnover_budget=3.0,
                         signal_frequency_trend=1.0,
                         edge_trend=1.0,
                         cooldown_active=False) -> FrequencyGate:
    """交易频率门。

    规则：
        1) daily_trades ≥ daily_limit → TIGHTENED（阈值上调）
        2) weekly_turnover ≥ weekly_turnover_limit → TIGHTENED
        3) signal_frequency_trend ↑ 且 edge_trend ↓ → WATCH
        4) portfolio_turnover ≥ budget 或 cooldown → HOLD
    """
    reasons = []
    threshold = 1.0
    mode = "NORMAL"
    allowed = True
    if int(daily_trades or 0) >= int(daily_limit or 0):
        reasons.append(f"DAILY_LIMIT({daily_trades}>={daily_limit})")
        threshold = 1.15
        mode = "TIGHTENED"
    if float(weekly_turnover or 0.0) >= float(weekly_turnover_limit or 0.0):
        reasons.append(f"WEEKLY_TURNOVER({weekly_turnover:.2f})")
        threshold = max(threshold, 1.2)
        mode = "TIGHTENED"
    if float(signal_frequency_trend or 1.0) > 1.3 \
            and float(edge_trend or 1.0) < 0.8:
        reasons.append("SIGNAL_NOISE(频率↑+边际↓)")
        mode = "WATCH"
        allowed = False
    if float(portfolio_turnover or 0.0) >= float(portfolio_turnover_budget
                                                 or 0.0) or cooldown_active:
        reasons.append("PORTFOLIO_TURNOVER_BUDGET" if
                       float(portfolio_turnover or 0.0) >=
                       float(portfolio_turnover_budget or 0.0)
                       else "COOLDOWN_ACTIVE")
        mode = "HOLD"
        allowed = False
    return FrequencyGate(allowed=allowed, mode=mode,
                         threshold_scale=round(threshold, 3),
                         reasons=tuple(reasons))
