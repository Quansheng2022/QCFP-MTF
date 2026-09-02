# coding: utf-8
"""周线信号合成测试"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.tactical.weekly_signal import build_signal


def _base(n=26, close=100.0, high=102.0, low=98.0, ema5=None, ema10=None, ema20=None):
    ema5 = ema5 or [close] * n
    ema10 = ema10 or [close] * n
    ema20 = ema20 or [close] * n
    return pd.DataFrame({
        "stock_code": ["00700"] * n,
        "date": pd.date_range("2026-01-02", periods=n, freq="W-FRI"),
        "close": [close] * n,
        "high": [high] * n,
        "low": [low] * n,
        "ema5": ema5,
        "ema10": ema10,
        "ema20": ema20,
    })


def _vol(breakout_last):
    n = 26
    vals = [0] * n
    if breakout_last:
        vals[-1] = 1
    return pd.DataFrame({
        "stock_code": ["00700"] * n,
        "week_end": pd.date_range("2026-01-02", periods=n, freq="W-FRI").strftime("%Y-%m-%d"),
        "w_volume_breakout": vals,
    })


def _vwap(dev_last=0.0):
    n = 26
    vals = [0.0] * n
    vals[-1] = dev_last
    return pd.DataFrame({
        "stock_code": ["00700"] * n,
        "week_end": pd.date_range("2026-01-02", periods=n, freq="W-FRI").strftime("%Y-%m-%d"),
        "w_vwap_deviation": vals,
    })


def test_breakout_three_confirm():
    base = _base(close=110.0, high=105.0, low=100.0)  # 最后行 close 110 > 前 20 周 high 105
    out = build_signal(base, _vol(True), _vwap(+0.05), DEFAULT_SETTINGS)
    assert out.iloc[-1]["w_breakout"] == 1
    assert out.iloc[-1]["tactical_signal"] == "Breakout"


def test_breakout_requires_volume():
    base = _base(close=110.0, high=105.0, low=100.0)
    out = build_signal(base, _vol(False), _vwap(+0.05), DEFAULT_SETTINGS)
    assert out.iloc[-1]["w_breakout"] == 0


def test_breakdown():
    base = _base(close=90.0, high=102.0, low=98.0)  # close 90 < 前 20 周 low 98
    out = build_signal(base, _vol(False), _vwap(-0.05), DEFAULT_SETTINGS)
    assert out.iloc[-1]["w_breakdown"] == 1
    assert out.iloc[-1]["tactical_signal"] == "Breakdown"


def test_pullback():
    n = 26
    base = _base(close=98.0, high=105.0, low=95.0,
                 ema5=[101.0] * n, ema10=[100.0] * n, ema20=[95.0] * n)
    out = build_signal(base, _vol(False), _vwap(0.0), DEFAULT_SETTINGS)
    assert out.iloc[-1]["tactical_signal"] == "Pullback"


def test_consolidation():
    n = 26
    base = _base(close=100.0, high=102.0, low=98.0,
                 ema5=[100.0] * n, ema10=[100.0] * n, ema20=[100.0] * n)
    out = build_signal(base, _vol(False), _vwap(0.0), DEFAULT_SETTINGS)
    assert out.iloc[-1]["tactical_signal"] == "Consolidation"


def test_slope_acceleration():
    n = 26
    ema5 = [float(100 + i * i * 0.5) for i in range(n)]  # 二阶差分为正常数 → 加速
    base = _base(close=130.0, ema5=ema5)
    out = build_signal(base, _vol(False), _vwap(0.0), DEFAULT_SETTINGS)
    assert out.iloc[-1]["w_ma_slope"] == "加速"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_weekly_signal 全部通过 ✅")
