# coding: utf-8
"""交易日历与周期切分测试"""

import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.common.calendar import TradingCalendar


def _sample_dates():
    # 2026-01-02(五) ~ 2026-01-30(五) 的完整交易日序列
    return [
        date(2026, 1, 2), date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 7),
        date(2026, 1, 8), date(2026, 1, 9), date(2026, 1, 12), date(2026, 1, 13),
        date(2026, 1, 14), date(2026, 1, 15), date(2026, 1, 16), date(2026, 1, 19),
        date(2026, 1, 20), date(2026, 1, 21), date(2026, 1, 22), date(2026, 1, 23),
        date(2026, 1, 26), date(2026, 1, 27), date(2026, 1, 28), date(2026, 1, 29),
        date(2026, 1, 30), date(2026, 3, 31), date(2026, 6, 30),
    ]


def test_week_end():
    cal = TradingCalendar(_sample_dates())
    # 2026-01-06(二) 所在 ISO 周结束日 2026-01-09(五)
    assert cal.period_end(date(2026, 1, 6), "weekly") == date(2026, 1, 9)


def test_month_end():
    cal = TradingCalendar(_sample_dates())
    assert cal.period_end(date(2026, 1, 15), "monthly") == date(2026, 1, 30)


def test_quarter_end():
    cal = TradingCalendar(_sample_dates())
    assert cal.period_end(date(2026, 2, 10), "quarterly") == date(2026, 3, 31)
    assert cal.period_end(date(2026, 5, 10), "quarterly") == date(2026, 6, 30)


def test_period_label():
    cal = TradingCalendar(_sample_dates())
    assert cal.period_label(date(2026, 1, 6), "monthly") == "2026-01"
    assert cal.period_label(date(2026, 1, 6), "quarterly") == "2026Q1"
    assert cal.period_label(date(2026, 1, 6), "weekly").startswith("2026W")


def test_split_periods():
    cal = TradingCalendar(_sample_dates())
    buckets = cal.split_periods(date(2026, 1, 5), date(2026, 1, 30), "weekly")
    # 1/5~1/30 覆盖 4 个自然周（1/2 周五单独成周，1/5 起 4 周）
    assert len(buckets) == 4


def test_prev_next():
    cal = TradingCalendar([date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 7)])
    assert cal.prev_trading_day(date(2026, 1, 8)) == date(2026, 1, 7)
    assert cal.next_trading_day(date(2026, 1, 1)) == date(2026, 1, 5)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_calendar 全部通过 ✅")
