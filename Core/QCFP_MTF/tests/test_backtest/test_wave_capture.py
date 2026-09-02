# coding: utf-8
"""Wave Capture 波段捕获指标测试"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.backtest.wave_capture import (false_entry_rate, find_waves,
                                            wave_capture_metrics,
                                            wave_capture_summary)


def _weekly_kl():
    """构造一只股票 52 周：前 20 周横盘 → 30 周翻倍（+100% 波段）"""
    dates = pd.date_range("2024-01-05", periods=52, freq="W-FRI")
    closes = [10.0] * 20 + [10 + 10 * i / 30 for i in range(1, 31)] + [20.0] * 2
    return pd.DataFrame({
        "stock_code": ["W1"] * 52,
        "date": dates,
        "close": closes,
    })


def _bt():
    """回测输出：波段期间第 25~45 周持仓（约 50% 涨幅处进入）"""
    closes = [10.0] * 20 + [10 + 10 * i / 30 for i in range(1, 31)] + [20.0] * 2
    rows = []
    for i in range(52):
        date = pd.date_range("2024-01-05", periods=52, freq="W-FRI")[i]
        in_wave = 25 <= i <= 45
        pos = 0.5 if in_wave else 0.0
        ret = (closes[i] / closes[i - 1] - 1) if i > 0 else 0.0
        rows.append({
            "stock_code": "W1",
            "week_end": date.strftime("%Y-%m-%d"),
            "position_start": pos,
            "pnl": pos * ret,
        })
    return pd.DataFrame(rows)


def test_find_waves():
    kl = _weekly_kl()
    waves = find_waves(kl, min_gain=0.5, window=26)
    assert len(waves) >= 1
    assert waves["gain"].max() >= 0.8   # 26 周窗口内最大波段 ≈ +83%
    assert (waves["stock_code"] == "W1").all()


def test_wave_capture_metrics():
    kl = _weekly_kl()
    waves = find_waves(kl, min_gain=0.5, window=26)
    bt = _bt()
    metrics = wave_capture_metrics(bt, waves)
    assert len(metrics) == len(waves)
    assert metrics["participated"].all()
    assert (metrics["entry_delay_weeks"] >= 0).all()
    assert metrics["capture_ratio"].notna().all()
    assert ((metrics["capture_ratio"] >= 0) & (metrics["capture_ratio"] <= 2.0)).all()
    assert (metrics["mfe"] >= 0).all()
    assert (metrics["mae"] <= 0).all()
    s = wave_capture_summary(metrics)
    assert s["n_waves"] == len(metrics)
    assert s["missed_wave_rate"] == 0.0


def test_false_entry_rate():
    kl = _weekly_kl()
    waves = find_waves(kl, min_gain=0.5, window=26)
    bt = _bt()
    # 在波段外加一次建仓 → 错误试仓率 > 0
    extra = bt.copy()
    extra.loc[5, "position_start"] = 0.3   # 波段（第 10+ 周起）之外的建仓
    rate = false_entry_rate(extra, waves)
    assert rate is not None and 0 < rate < 1


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_wave_capture 全部通过 ✅")
