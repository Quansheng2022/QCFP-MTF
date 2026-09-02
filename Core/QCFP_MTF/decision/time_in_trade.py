# coding: utf-8
"""Time-in-Trade Governance（QCFP-MTF 2.8：持仓时间治理）

回答"这笔交易持有多久了、是否还应该继续持有"：
    expected_holding_days  预期持有期（由历史分布校准）
    max_holding_days       最大持有期（超期未扩张 → Time Exit/Reduce）
    last_confirmation_date 最后确认日（长时间无新确认 → 机会衰减）

输出三档建议：
    HOLD            未超期且有扩张/确认
    REDUCE          超预期期但仍有趋势存活权 → 减仓观察
    EXIT            超最大期且无扩张 → 离场

本模块只产生建议，最终动作由 FSM / action_gate 决定。
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class TimeInTrade:
    holding_days: int
    expected_holding_days: int
    max_holding_days: int
    days_since_confirmation: int
    progress_since_entry: float    # 进场以来涨幅（比例，负=亏损）
    status: str                    # HOLD / REDUCE / EXIT
    reason: str
    last_confirmation_date: str = ""
    entry_date: str = ""
    reasons: tuple = field(default_factory=tuple)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["reasons"] = list(self.reasons)
        return d


def _days(start: str, end: str) -> int:
    try:
        d1 = datetime.strptime(str(start)[:10], "%Y-%m-%d")
        d2 = datetime.strptime(str(end)[:10], "%Y-%m-%d")
        return max(0, (d2 - d1).days)
    except Exception:
        return 0


def evaluate_time_in_trade(
        entry_date, decision_date,
        expected_holding_days=45,
        max_holding_days=90,
        last_confirmation_date=None,
        progress_since_entry=None,
        no_confirmation_grace_days=30) -> TimeInTrade:
    """评估持仓时间状态。

    规则：
        holding > max → EXIT（除非 progress > 0 且最近有确认 → REDUCE）
        holding > expected 且无扩张 → REDUCE
        否则 HOLD
    """
    holding = _days(entry_date, decision_date)
    confirm_date = last_confirmation_date or entry_date
    since_confirm = _days(confirm_date, decision_date)
    progress = float(progress_since_entry or 0.0)
    reasons = []

    over_max = holding > max_holding_days
    over_expected = holding > expected_holding_days
    stale = since_confirm > no_confirmation_grace_days

    if over_max:
        if progress > 0.05 and not stale:
            status, reason = "REDUCE", \
                f"超最大持有期({holding}>{max_holding_days})但有扩张，减仓观察"
        else:
            status, reason = "EXIT", \
                f"超过最大持有期({holding}>{max_holding_days})且无扩张证据"
        reasons.append("MAX_HOLDING_EXCEEDED")
    elif over_expected:
        if progress <= 0.0:
            status, reason = "REDUCE", \
                f"超过预期持有期({holding}>{expected_holding_days})且无盈利"
        else:
            status, reason = "HOLD", \
                f"超过预期持有期({holding}>{expected_holding_days})但趋势存活"
        reasons.append("EXPECTED_HOLDING_EXCEEDED")
    else:
        status, reason = "HOLD", f"持有 {holding} 天，未超预期"

    if stale:
        reasons.append(f"NO_CONFIRMATION_{since_confirm}D")
        if status == "HOLD":
            status = "REDUCE"
            reason = f"长时间无新确认（{since_confirm} 天），减仓观察"

    return TimeInTrade(
        holding_days=holding,
        expected_holding_days=expected_holding_days,
        max_holding_days=max_holding_days,
        days_since_confirmation=since_confirm,
        progress_since_entry=round(progress, 4),
        status=status, reason=reason,
        last_confirmation_date=confirm_date,
        entry_date=entry_date,
        reasons=tuple(reasons))
