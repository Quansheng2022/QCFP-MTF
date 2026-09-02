# coding: utf-8
"""港股交易日历与 周/月/季 周期切分对齐工具

数据底座驱动：以 hk_hist_daily_kline 中的实际交易日作为交易日历，
与项目"数据优先"的约定一致；无数据时退化为周一~周五自然日。
"""

import sqlite3
from datetime import date, datetime, timedelta
from typing import List, Tuple

from .db import connect

PERIODS = ("daily", "weekly", "monthly", "quarterly")


def _to_date(d) -> date:
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    return datetime.strptime(str(d), "%Y-%m-%d").date()


class TradingCalendar:
    """基于实际交易日的港股日历"""

    def __init__(self, dates: List[date]):
        self._dates = sorted(set(_to_date(d) for d in dates))

    @classmethod
    def from_db(cls, db_path=None) -> "TradingCalendar":
        conn = connect(db_path)
        try:
            rows = conn.execute(
                "SELECT DISTINCT date FROM hk_hist_daily_kline ORDER BY date"
            ).fetchall()
        finally:
            conn.close()
        return cls([r[0] for r in rows])

    @property
    def dates(self) -> List[date]:
        return self._dates

    def is_empty(self) -> bool:
        return len(self._dates) == 0

    def is_trading_day(self, d) -> bool:
        d = _to_date(d)
        if not self.is_empty():
            return d in self._dates
        return d.weekday() < 5

    def prev_trading_day(self, d) -> date:
        """d 当天或之前最近的一个交易日"""
        d = _to_date(d)
        if not self.is_empty():
            idx = len(self._dates) - 1
            while idx >= 0 and self._dates[idx] > d:
                idx -= 1
            return self._dates[max(idx, 0)]
        while d.weekday() >= 5:
            d -= timedelta(days=1)
        return d

    def next_trading_day(self, d) -> date:
        """d 当天或之后最近的一个交易日"""
        d = _to_date(d)
        if not self.is_empty():
            for td in self._dates:
                if td >= d:
                    return td
            return self._dates[-1]
        while d.weekday() >= 5:
            d += timedelta(days=1)
        return d

    # ---------------- 周期切分 ----------------
    def period_start(self, d, period: str) -> date:
        d = _to_date(d)
        if period == "weekly":
            start = d - timedelta(days=d.weekday())
        elif period == "monthly":
            start = d.replace(day=1)
        elif period == "quarterly":
            q_start_month = ((d.month - 1) // 3) * 3 + 1
            start = d.replace(month=q_start_month, day=1)
        else:
            start = d
        return self.next_trading_day(start) if not self.is_empty() else start

    def period_end(self, d, period: str) -> date:
        """d 所在周期的最后一个交易日"""
        d = _to_date(d)
        end = self._natural_period_end(d, period)

        # 周期内最后一个交易日：不超过自然周期结束日
        if not self.is_empty():
            candidates = [td for td in self._dates if td <= end]
            if candidates:
                return candidates[-1]
            return self.period_start(d, period)
        while end.weekday() >= 5:
            end -= timedelta(days=1)
        return end

    def _natural_period_end(self, d: date, period: str) -> date:
        """d 所在周期的自然结束日（不含交易日约束）"""
        d = _to_date(d)
        if period == "weekly":
            return d + timedelta(days=6 - d.weekday())
        if period == "monthly":
            if d.month == 12:
                return d.replace(year=d.year + 1, month=1, day=1) - timedelta(days=1)
            return d.replace(month=d.month + 1, day=1) - timedelta(days=1)
        if period == "quarterly":
            q_end_month = ((d.month - 1) // 3) * 3 + 3
            if q_end_month == 12:
                return d.replace(year=d.year + 1, month=1, day=1) - timedelta(days=1)
            return d.replace(month=q_end_month + 1, day=1) - timedelta(days=1)
        return d

    def period_label(self, d, period: str) -> str:
        d = _to_date(d)
        if period == "weekly":
            iso = d.isocalendar()
            return f"{iso[0]}W{iso[1]:02d}"
        if period == "monthly":
            return d.strftime("%Y-%m")
        if period == "quarterly":
            return f"{d.year}Q{(d.month - 1) // 3 + 1}"
        return d.strftime("%Y-%m-%d")

    def split_periods(self, start, end, period: str) -> List[Tuple[str, date, date]]:
        """把 [start, end] 切分为若干 (label, period_start, period_end)"""
        start = _to_date(start)
        end = _to_date(end)
        buckets = []
        cursor = start
        while cursor <= end:
            ps = self.period_start(cursor, period)
            pe = self.period_end(cursor, period)
            label = self.period_label(pe, period)
            if not buckets or buckets[-1][0] != label:
                buckets.append((label, ps, pe))
            # 按自然周期结束日的次日推进，避免周末/节假日造成死循环
            cursor = self._natural_period_end(cursor, period) + timedelta(days=1)
        return buckets


def build_calendar(db_path=None) -> TradingCalendar:
    """便捷函数：从数据库构建交易日历"""
    return TradingCalendar.from_db(db_path)
