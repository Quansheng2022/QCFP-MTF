# coding: utf-8
"""Opportunity Queue / Watchlist（QCFP-MTF 2.8：55 号机会队列）

不是所有好机会都应立即交易，队列管理等待高质量入场：
    WATCH / TEST / READY / ACTIVE / BLOCKED / EXPIRED

例：Wave=STRONG + Permission=TEST + Entry=LATE → WATCHLIST；
    回调后 Entry=OPTIMAL + Permission=ALLOW → READY。
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime


QUEUE_STATES = ("WATCH", "TEST", "READY", "ACTIVE", "BLOCKED", "EXPIRED")


@dataclass(frozen=True)
class QueueItem:
    stock_code: str
    state: str = "WATCH"
    score: float = 0.0
    permission: str = "WATCH"
    entry_timing: str = ""
    wave_stage: str = ""
    added_at: str = ""
    updated_at: str = ""
    reasons: tuple = field(default_factory=tuple)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["reasons"] = list(self.reasons)
        return d


def evaluate_queue_status(permission="WATCH", entry_timing="",
                          wave_stage="", score=0.0,
                          age_days=0, max_age_days=90,
                          blocked=False) -> tuple:
    """机会 → 队列状态。

    规则：
        blocked / permission=BLOCK         → BLOCKED
        age > max_age / wave INVALID       → EXPIRED
        permission in (ALLOW, STRONG_ALLOW) + entry=OPTIMAL
                                           → READY
        permission in (TEST,)              → TEST
        permission in (ALLOW,) + entry∈EARLY/ACCEPTABLE
                                           → WATCH（等更好位置）
        其余                                → WATCH
    返回 (state, reasons)。
    """
    reasons = []
    if blocked or permission == "BLOCK":
        return "BLOCKED", ["PERMISSION_BLOCK"]
    if age_days > max_age_days or str(wave_stage or "").upper() == "INVALID":
        return "EXPIRED", [f"AGE_{age_days}>MAX" if age_days > max_age_days
                           else "WAVE_INVALID"]
    if permission in ("ALLOW", "STRONG_ALLOW"):
        if entry_timing == "OPTIMAL":
            return "READY", ["ENTRY_OPTIMAL_ALLOW"]
        if entry_timing in ("EARLY", "ACCEPTABLE"):
            return "WATCH", [f"ENTRY_{entry_timing}_WAIT_BETTER"]
        return "WATCH", ["ENTRY_NOT_OPTIMAL"]
    if permission == "TEST":
        return "TEST", ["PERMISSION_TEST_EXPLORE"]
    return "WATCH", ["PERMISSION_WATCH"]


class OpportunityQueue:
    def __init__(self):
        self.items = {}

    def add_or_update(self, stock_code, **kw) -> QueueItem:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        existing = self.items.get(stock_code)
        item = QueueItem(
            stock_code=stock_code,
            state=kw.get("state") or (existing.state if existing
                                      else "WATCH"),
            score=float(kw.get("score") or (existing.score if existing
                                            else 0.0)),
            permission=kw.get("permission") or (
                existing.permission if existing else "WATCH"),
            entry_timing=kw.get("entry_timing") or (
                existing.entry_timing if existing else ""),
            wave_stage=kw.get("wave_stage") or (
                existing.wave_stage if existing else ""),
            added_at=existing.added_at if existing else now,
            updated_at=now,
            reasons=tuple(kw.get("reasons") or []))
        self.items[stock_code] = item
        return item

    def auto_update(self, stock_code, permission, entry_timing,
                    wave_stage="", score=0.0, age_days=0,
                    max_age_days=90, blocked=False) -> QueueItem:
        """按条件自动推进队列状态。"""
        state, reasons = evaluate_queue_status(
            permission=permission, entry_timing=entry_timing,
            wave_stage=wave_stage, score=score, age_days=age_days,
            max_age_days=max_age_days, blocked=blocked)
        return self.add_or_update(
            stock_code, state=state, permission=permission,
            entry_timing=entry_timing, wave_stage=wave_stage,
            score=score, reasons=reasons)

    def ready(self) -> list:
        return [s for s, i in self.items.items() if i.state == "READY"]

    def summary(self) -> dict:
        from collections import Counter
        return dict(Counter(i.state for i in self.items.values()))
