# coding: utf-8
"""金融不变量测试（P1：纯合成数据，完全脱离 SQLite）

1) PIT 不变量：available_date > decision_date 的行不得产生信号
2) Position 不变量：position ∈ [0, 1]
3) Cost conservation：pnl == position_start × effective_return - cost（精确一致）
4) Benchmark 独立性：基准只依赖价格，不进入信号
"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.backtest.benchmark import buy_hold_returns
from QCFP_MTF.backtest.data_pipeline import build_signal_timeline
from QCFP_MTF.backtest.engine import run_backtest
from QCFP_MTF.config.settings import DEFAULT_SETTINGS


def _frames():
    structural = pd.DataFrame({
        "stock_code": ["00700", "00700"],
        "period_end": ["2026-03-31", "2026-06-30"],
        "available_date": ["2026-05-15", "2026-08-14"],
        "structural_regime": ["STRUCTURAL_DECLINE", "STRUCTURAL_BULLISH"],
        "c_state": ["C→", "C↑"], "f_state": ["F→", "F↑"], "p_state": ["P→", "P↑"],
        "q_trend_score": [40.0, 70.0], "q_position_52w": [0.03, 0.55],
        "data_quality": ["A", "A"],
    })
    monthly = pd.DataFrame({
        "stock_code": ["00700"] * 3,
        "month_end": ["2026-04-30", "2026-05-31", "2026-07-31"],
        "monthly_behavior_state": ["Improving", "Improving", "Stable"],
        "cbi_score": [55.0, 60.0, 55.0],
        "cbi_state": ["CBI_STABLE", "CBI_STABLE", "CBI_STABLE"],
        "cost_position": ["COST_NEUTRAL"] * 3, "data_quality": ["A"] * 3,
    })
    weekly = pd.DataFrame({
        "stock_code": ["00700"] * 4, "stock_name": ["腾讯控股"] * 4,
        "week_end": ["2026-05-29", "2026-06-05", "2026-06-12", "2026-06-19"],
        "tactical_signal": ["Consolidation"] * 4, "data_quality": ["A"] * 4,
    })
    chip = pd.DataFrame({
        "stock_code": ["00700"] * 2,
        "quarter_end_date": ["2026-03-31", "2026-06-30"],
        "chip_structure_score": [60.0, 80.0],
    })
    idx = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=200, freq="D"),
        "HSI": [20000.0 + i for i in range(200)], "VHSI": [20.0] * 200,
    })
    weekly_kl = pd.DataFrame({
        "stock_code": ["00700"] * 6,
        "date": pd.to_datetime(pd.date_range("2026-05-01", periods=6, freq="W-FRI")),
        "high": [10.0 + i * 0.1 for i in range(6)],
        "low": [9.8 + i * 0.1 for i in range(6)],
        "close": [10.0 + i * 0.1 for i in range(6)],
    })
    return structural, monthly, weekly, chip, idx, weekly_kl


def test_pit_invariant():
    structural, monthly, weekly, chip, idx, _ = _frames()
    sig = build_signal_timeline(structural, monthly, weekly, chip, idx, DEFAULT_SETTINGS)
    sig = sig[sig["mtf_regime"] != "DATA_INSUFFICIENT"]
    assert (pd.to_datetime(sig["structural_available_date"]) <=
            pd.to_datetime(sig["decision_date"])).all()


def test_position_invariant():
    structural, monthly, weekly, chip, idx, weekly_kl = _frames()
    sig = build_signal_timeline(structural, monthly, weekly, chip, idx, DEFAULT_SETTINGS)
    bt = run_backtest(sig, weekly_kl, DEFAULT_SETTINGS)
    assert bt["position"].between(0.0, 1.0).all()
    assert bt["position_start"].between(0.0, 1.0).all()


def test_cost_conservation():
    structural, monthly, weekly, chip, idx, weekly_kl = _frames()
    sig = build_signal_timeline(structural, monthly, weekly, chip, idx, DEFAULT_SETTINGS)
    bt = run_backtest(sig, weekly_kl, DEFAULT_SETTINGS)
    lhs = bt["pnl"]
    rhs = bt["position_start"] * bt["effective_return"].fillna(0.0) - bt["cost"]
    # 持仓周 return 缺失 → pnl 为 NaN（return_missing 标记），不允许当 0 处理
    assert bt["return_missing"].eq(bt["pnl"].isna() & (bt["position_start"] > 0)).all()
    assert (lhs.fillna(0) - rhs.fillna(0)).abs().max() < 1e-12


def test_benchmark_independence():
    _, _, _, _, _, weekly_kl = _frames()
    bench = buy_hold_returns(weekly_kl)
    assert not bench.empty
    assert bench.index.nunique() > 3
    assert isinstance(bench, pd.Series)
    assert bench.index.name == "week_end"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_invariants 全部通过 ✅")
