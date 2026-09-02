# coding: utf-8
"""金融不变量测试（P0 补充，纯合成数据）

1) 止损后无未来 PnL 暴露（position_start 退出后必须为 0）
2) 缺失收益绝不变成 0（return_missing 标记，pnl=NaN）
3) 缺失收益不改变组合分母（n_missing_return 计数）
4) PIT Universe 重叠区间 → validate_universe > 0
5) research_validation 模式缺 universe → run_status FAILED
"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.backtest.engine import portfolio_returns, run_backtest
from QCFP_MTF.backtest.pit_universe import validate_universe
from QCFP_MTF.backtest.run_status import run_status
from QCFP_MTF.config.settings import DEFAULT_SETTINGS, _deep_merge


def _sig(targets, dates):
    return pd.DataFrame({
        "stock_code": ["00700"] * len(dates),
        "decision_date": dates,
        "action_signal": ["HOLD"] * len(dates),
        "mtf_regime": ["BULLISH_STABLE"] * len(dates),
        "market_regime": ["neutral"] * len(dates),
        "structural_regime": ["STRUCTURAL_BULLISH"] * len(dates),
        "is_override": [True] * len(dates),
        "structural_available_date": ["2026-05-15"] * len(dates),
        "target": targets,
    })


def test_stop_loss_flat_after_exit():
    sig = _sig([0.2, 0.2, 0.2, 0.2],
               ["2024-02-09", "2024-02-16", "2024-02-23", "2024-03-01"])
    weekly = pd.DataFrame({
        "stock_code": ["00700"] * 4,
        "date": pd.to_datetime(["2024-02-09", "2024-02-16", "2024-02-23", "2024-03-01"]),
        "low": [9.0, 10.0, 9.5, 11.0],
        "close": [9.5, 10.5, 9.4, 12.0],
    })
    bt = run_backtest(sig, weekly, DEFAULT_SETTINGS)
    assert bt.iloc[2]["position_start"] > 0
    assert bt.iloc[3]["position_start"] == 0.0
    assert abs(bt.iloc[3]["pnl"] - (-bt.iloc[3]["cost"])) < 1e-12


def test_missing_return_never_becomes_zero():
    sig = _sig([0.5, 0.5], ["2026-05-22", "2026-05-29"])
    weekly = pd.DataFrame({
        "stock_code": ["00700"],
        "date": pd.to_datetime(["2026-05-29"]),
        "low": [10.0], "close": [10.0],
    })
    bt = run_backtest(sig, weekly, DEFAULT_SETTINGS)
    assert bt.iloc[0]["position_start"] == 0.5
    assert bool(bt.iloc[0]["return_missing"]) is True
    assert pd.isna(bt.iloc[0]["pnl"])


def test_missing_return_never_changes_denominator():
    sig = _sig([0.5, 0.5], ["2026-05-22", "2026-05-29"])
    weekly = pd.DataFrame({
        "stock_code": ["00700"],
        "date": pd.to_datetime(["2026-05-29"]),
        "low": [10.0], "close": [10.0],
    })
    bt = run_backtest(sig, weekly, DEFAULT_SETTINGS)
    port = portfolio_returns(bt)
    assert int(port["n_missing_return"].iloc[0]) == 1


def test_universe_overlap_detected():
    universe = pd.DataFrame({
        "stock_code": ["00001", "00001"],
        "valid_from": ["2020-01-01", "2021-01-01"],
        "valid_to": ["2022-01-01", "2023-01-01"],
    })
    assert validate_universe(universe) == 1


def test_validation_mode_requires_universe():
    settings = _deep_merge(DEFAULT_SETTINGS, {"backtest": {"mode": "research_validation"}})
    status = run_status(settings, universe_empty=True)
    assert status["status"] == "FAILED"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_financial_invariants 全部通过 ✅")
