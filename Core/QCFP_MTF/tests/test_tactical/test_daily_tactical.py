# coding: utf-8
"""日线战术层（L4）单元测试"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.tactical.daily_tactical import (build_daily_states,
                                              build_flow_factors,
                                              build_price_factors)


def _kline(n=70):
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    # 先横盘（前 25 日），随后放量突破上行（后 20 日），再高位滞涨（最后 10 日）
    close = [10.0 + i * 0.01 for i in range(25)]
    close += [10.5 + i * 0.08 for i in range(20)]          # 突破上行
    close += [12.1 + i * 0.02 for i in range(25 - 45)] if n > 45 else []
    while len(close) < n:
        close.append(close[-1] + 0.01)
    close = close[:n]
    vol = [1_000_000] * 25 + [2_500_000] * 20 + [1_200_000] * (n - 45)
    df = pd.DataFrame({
        "stock_code": ["00700"] * n,
        "date": dates,
        "open": close,
        "high": [c + 0.05 for c in close],
        "low": [c - 0.05 for c in close],
        "close": close,
        "volume": vol,
        "amount": [c * v for c, v in zip(close, vol)],
    })
    return df


def test_price_factors_and_breakout():
    p = build_price_factors(_kline(), DEFAULT_SETTINGS)
    p = p.sort_values("date").reset_index(drop=True)
    # 突破段（第 25~44 日）应出现 d_breakout=1；前期横盘段不应出现
    first_break = p.index[p["d_breakout"] == 1].min()
    assert first_break >= 25, f"突破不应早于 25 日（实际 {first_break}）"
    assert (p["d_trend_score"] >= 0).all() and (p["d_trend_score"] <= 100).all()
    assert p["d_vol_ratio"].iloc[27] > 1.5


def test_flow_factors_pit():
    # 资金流随时间递增（前 40 日低、后 40 日高），保证滚动 std>0
    inflow = [50.0 + 2.0 * i for i in range(80)]
    mf = pd.DataFrame({
        "stock_code": ["00700"] * 80,
        "date": pd.date_range("2024-01-01", periods=80, freq="D"),
        "capital_in_super": inflow,
        "capital_in_big": [x * 0.5 for x in inflow],
        "capital_out_super": [60.0] * 80,
        "capital_out_big": [40.0] * 80,
    })
    f = build_flow_factors(mf, DEFAULT_SETTINGS)
    assert f is not None
    # 前 20 日无足够窗口 → flow_z 为 NaN（PIT 窗口保护）
    assert f["d_flow_z"].iloc[:19].isna().all()
    assert f["d_flow_z"].iloc[70] > 0


def test_states_order():
    k = _kline()
    p = build_price_factors(k, DEFAULT_SETTINGS)
    n = len(k)
    inflow = [100.0 + i for i in range(n)]
    f = build_flow_factors(pd.DataFrame({
        "stock_code": ["00700"] * n,
        "date": pd.to_datetime(k["date"]),
        "capital_in_super": inflow,
        "capital_in_big": [x * 0.5 for x in inflow],
        "capital_out_super": [80.0] * n,
        "capital_out_big": [70.0] * n,
    }), DEFAULT_SETTINGS)
    states = build_daily_states(p, f, DEFAULT_SETTINGS)
    s = states.set_index("trade_date")["daily_state"]
    # 前期横盘+资金改善 → 吸筹/中性；突破段 → BREAKOUT；滞涨段 → DISTRIBUTION/PULLBACK
    mid = s.iloc[30]
    assert mid in ("DAILY_BREAKOUT", "DAILY_ACCUMULATION", "DAILY_NEUTRAL")
    assert (s == "DAILY_BREAKOUT").sum() >= 1
    assert set(s.unique()) <= {
        "DAILY_ACCUMULATION", "DAILY_BREAKOUT", "DAILY_PULLBACK",
        "DAILY_DISTRIBUTION", "DAILY_DECLINE", "DAILY_NEUTRAL"}


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_daily_tactical 全部通过 ✅")
