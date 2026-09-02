# coding: utf-8
"""WaveLabel（QCFP-MTF 2.6：评价标签，仅 Evaluation 层使用）

WaveLabel 使用未来 26 周 peak 定义，是未来信息标签——
**只允许用于 Evaluation，禁止进入 Decision Engine**（Feature Gate 强制）。
"""

from dataclasses import dataclass

from ..backtest.wave_capture import find_waves


@dataclass(frozen=True)
class WaveLabel:
    stock_code: str
    start_date: str
    peak_date: str
    end_date: str
    gain: float
    future_aware: bool = True


def find_wave_labels(weekly_df, min_gain=0.5, window=26):
    """26 周窗口涨幅 >= min_gain 的波段标签（future-aware，仅评价用）"""
    w = find_waves(weekly_df, min_gain=min_gain, window=window)
    return [WaveLabel(stock_code=r["stock_code"], start_date=r["start_date"],
                      peak_date=r["peak_date"], end_date=r["end_date"],
                      gain=float(r["gain"]))
            for _, r in w.iterrows()]
