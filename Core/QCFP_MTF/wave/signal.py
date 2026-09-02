# coding: utf-8
"""WaveSignal（QCFP-MTF 2.6：波段信号，as-of 可用，允许进入 Decision 层）

与 WaveLabel（future-aware，仅评价）严格隔离：
    WaveSignal 只使用截至当前时点（含）的价格数据，可进入 Wave/Decision 层。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class WaveSignal:
    direction: str        # UP / DOWN / SIDEWAYS
    strength: float       # 0.0 ~ 1.0（过去 lookback 周趋势强度）
    age: int              # 当前趋势已持续周数
    acceleration: float   # 最近 3 周斜率 - 前 3 周斜率
    recovery: bool        # 近期从低位反弹（as-of）
    failure: bool         # 近期高位回落破位（as-of）
    future_aware: bool = False


def evaluate_wave_signal(closes, lookback: int = 13) -> WaveSignal:
    """基于截至当前的价格序列计算 as-of WaveSignal（无未来信息）"""
    import numpy as np
    x = [float(c) for c in closes]
    n = len(x)
    if n < 4:
        return WaveSignal("SIDEWAYS", 0.0, 0, 0.0, False, False)
    w = x[-min(lookback, n):]
    total = (w[-1] - w[0]) / w[0] if w[0] > 0 else 0.0
    strength = float(max(0.0, min(1.0, abs(total) / 0.5)))
    direction = "UP" if total > 0.02 else "DOWN" if total < -0.02 else "SIDEWAYS"
    # 趋势年龄：连续同向周数
    age = 0
    for i in range(len(x) - 1, 0, -1):
        if direction == "UP" and x[i] > x[i - 1]:
            age += 1
        elif direction == "DOWN" and x[i] < x[i - 1]:
            age += 1
        else:
            break
    # 加速度：最近 3 周斜率 vs 前 3 周斜率
    def _slope(seg):
        if len(seg) < 2 or seg[0] == 0:
            return 0.0
        return (seg[-1] - seg[0]) / seg[0]
    accel = _slope(x[-3:]) - _slope(x[-6:-3]) if n >= 6 else 0.0
    low_recent = min(x[-4:]) if n >= 4 else min(x)
    recovery = bool(n >= 6 and x[-1] > x[-2] and x[-2] <= low_recent * 1.02)
    failure = bool(n >= 6 and x[-1] < x[-2] and x[-2] >= max(x[-6:-2]) * 0.98)
    return WaveSignal(direction, round(strength, 3), age,
                      round(float(accel), 3), recovery, failure)
