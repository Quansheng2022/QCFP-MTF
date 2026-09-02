# coding: utf-8
"""回测引擎测试（仓位 shift / 换仓成本 / pnl）"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.backtest.engine import run_backtest
from QCFP_MTF.config.settings import DEFAULT_SETTINGS


def _data():
    signals = pd.DataFrame({
        "stock_code": ["00700"] * 3,
        "decision_date": ["2026-01-09", "2026-01-16", "2026-01-23"],
        "action_signal": ["BUY", "HOLD", "EXIT"],
        "mtf_regime": ["BULLISH_CONFIRMED", "BULLISH_STABLE", "BEARISH_CONFIRMED"],
        "market_regime": ["risk_on", "risk_on", "risk_off"],
        "structural_regime": ["STRUCTURAL_BULLISH"] * 3,
    })
    weekly = pd.DataFrame({
        "stock_code": ["00700"] * 4,
        "date": pd.to_datetime(["2026-01-02", "2026-01-09", "2026-01-16", "2026-01-23"]),
        "close": [100.0, 110.0, 115.5, 103.95],
    })
    return signals, weekly


def test_position_shift_and_pnl():
    signals, weekly = _data()
    out = run_backtest(signals, weekly, DEFAULT_SETTINGS)
    # 周收益：+10%, +5%, -10%
    assert abs(out.iloc[0]["weekly_return"] - 0.10) < 1e-9
    assert abs(out.iloc[1]["weekly_return"] - 0.05) < 1e-9
    # 仓位下一周生效：第 1 周 0（BUY 信号次周生效），第 2 周 1.0
    # 第 3 周仍是 1.0（EXIT 信号第 3 周发出，第 4 周才生效）
    assert out.iloc[0]["position"] == 0.0
    assert out.iloc[1]["position"] == 1.0
    assert out.iloc[2]["position"] == 1.0
    # 第 2 周：建仓（买入费率 0.35%）；pnl = 1.0*0.05 - 0.0035
    buy = 0.0025 + 0.001
    assert abs(out.iloc[1]["cost"] - buy) < 1e-9
    assert abs(out.iloc[1]["pnl"] - (0.05 - buy)) < 1e-9
    # 第 3 周：持仓 1.0 承受 -10% 收益，无换仓
    assert out.iloc[2]["cost"] == 0.0
    assert abs(out.iloc[2]["pnl"] - (-0.10)) < 1e-9


def test_trailing_stop_exits_override_run():
    # 试多持仓跌破建仓周最低价×(1-buffer) → 周收盘确认 → 次周离场；
    # 确认周完整承受周收益（持仓至收盘），期末仓位归零
    signals = pd.DataFrame({
        "stock_code": ["01951"] * 4,
        "decision_date": ["2024-02-09", "2024-02-16", "2024-02-23", "2024-03-01"],
        "action_signal": ["REDUCE"] * 4,
        "mtf_regime": ["BULLISH_WARNING"] * 4,
        "market_regime": ["neutral"] * 4,
        "structural_regime": ["STRUCTURAL_DECLINE"] * 4,
        "is_override": [True] * 4,
        "structural_available_date": ["2024-02-14"] * 4,
        "target": [0.2] * 4,
    })
    weekly = pd.DataFrame({
        "stock_code": ["01951"] * 4,
        "date": pd.to_datetime(["2024-02-09", "2024-02-16", "2024-02-23", "2024-03-01"]),
        "low": [9.0, 10.0, 9.5, 11.0],
        "close": [9.5, 10.5, 9.4, 12.0],   # 第 3 周收盘 9.4 < 10.0×0.98 → 止损
    })
    out = run_backtest(signals, weekly, DEFAULT_SETTINGS)
    # 仓位次周生效：第 1 周 0，第 2 周 0.2（建仓周 low=10.0）
    assert out.iloc[0]["position"] == 0.0
    assert out.iloc[1]["position"] == 0.2
    # 第 3 周收盘 9.4 < 9.8 → 止损确认，期末仓位归零，周初仓位 0.2（完整周收益照记）
    assert out.iloc[2]["position"] == 0.0
    assert abs(out.iloc[2]["position_start"] - 0.2) < 1e-9
    # 第 4 周虽 target 仍 0.2，但同段试多内已止损 → 保持 0
    assert out.iloc[3]["position"] == 0.0
    assert out.iloc[3]["position_start"] == 0.0      # 无未来暴露
    assert abs(out.iloc[3]["pnl"] - (-out.iloc[3]["cost"])) < 1e-12
    # 确认周有效收益 = 周收益（9.4/10.5 - 1），不按止损价成交
    assert abs(out.iloc[2]["effective_return"] - (9.4 / 10.5 - 1)) < 1e-9
    # 成本守恒：pnl = position_start × effective_return - cost
    assert abs(out.iloc[2]["pnl"] -
               (0.2 * (9.4 / 10.5 - 1) - out.iloc[2]["cost"])) < 1e-12


def test_trend_survival_widens_holding_stop():
    """2.4 趋势存活权：HOLDING 状态持仓使用更宽存活缓冲（5%），不被正常波动甩下"""
    signals = pd.DataFrame({
        "stock_code": ["01951"] * 4,
        "decision_date": ["2024-02-09", "2024-02-16", "2024-02-23", "2024-03-01"],
        "action_signal": ["REDUCE"] * 4,
        "mtf_regime": ["BULLISH_WARNING"] * 4,
        "market_regime": ["neutral"] * 4,
        "structural_regime": ["STRUCTURAL_DECLINE"] * 4,
        "is_override": [True] * 4,
        "structural_available_date": ["2024-02-14"] * 4,
        "fsm_state": ["HOLDING"] * 4,
        "target": [0.2] * 4,
    })
    weekly = pd.DataFrame({
        "stock_code": ["01951"] * 4,
        "date": pd.to_datetime(["2024-02-09", "2024-02-16", "2024-02-23", "2024-03-01"]),
        "low": [9.0, 10.0, 9.5, 11.0],
        "close": [9.5, 10.5, 9.6, 12.0],   # -4% 波动：默认 2% 会止损，存活缓冲 5% 不触发
    })
    out = run_backtest(signals, weekly, DEFAULT_SETTINGS)
    # 第 3 周收盘 9.6 ≥ 10.0×0.95 → 存活，仓位保持 0.2
    assert abs(out.iloc[2]["position"] - 0.2) < 1e-9
    assert abs(out.iloc[2]["position_start"] - 0.2) < 1e-9


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_engine 全部通过 ✅")
