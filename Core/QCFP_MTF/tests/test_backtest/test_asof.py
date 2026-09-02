# coding: utf-8
"""Validation Hardening 金融逻辑测试：
as-of 对齐 / chip look-ahead / CBI 标准化无未来泄漏 / 组合核算 / 成本方向 / 权重归一化
"""

import copy
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.backtest.cost_model import buy_rate, sell_rate
from QCFP_MTF.backtest.cross_sectional import cross_sectional_portfolio
from QCFP_MTF.backtest.data_pipeline import build_signal_timeline
from QCFP_MTF.backtest.engine import portfolio_returns, run_backtest
from QCFP_MTF.behavioral.cbi import build_cbi
from QCFP_MTF.common.asof import asof_join_latest
from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.fusion.chip_confidence import compute_chip_confidence


def _struct():
    return pd.DataFrame({
        "stock_code": ["00700", "00700"],
        "period_end": ["2026-03-31", "2026-06-30"],
        "available_date_dt": pd.to_datetime(["2026-05-15", "2026-08-15"]),
        "structural_regime": ["STRUCTURAL_DECLINE", "STRUCTURAL_BULLISH"],
    })


def test_structural_asof_uses_available_not_period_end():
    # 决策 2026-07-10：06-30 季度（披露 08-15）不可用，只能用 03-31 季度
    grid = pd.DataFrame({"stock_code": ["00700"],
                         "decision_dt": pd.to_datetime(["2026-07-10"])})
    out = asof_join_latest(grid, _struct(), "decision_dt", "available_date_dt",
                           right_cols=["period_end", "structural_regime"])
    assert out.iloc[0]["structural_regime"] == "STRUCTURAL_DECLINE"
    assert out.iloc[0]["period_end"] == "2026-03-31"


def test_chip_lookahead():
    chip = pd.DataFrame({
        "stock_code": ["00700", "00700"],
        "quarter_end_date": ["2026-03-31", "2026-06-30"],
        "available_date_dt": pd.to_datetime(["2026-05-15", "2026-08-15"]),
        "chip_structure_score": [50.0, 80.0],
    })
    grid = pd.DataFrame({"stock_code": ["00700"],
                         "decision_dt": pd.to_datetime(["2026-07-10"])})
    out = asof_join_latest(grid, chip, "decision_dt", "available_date_dt",
                           right_cols=["chip_structure_score"])
    assert out.iloc[0]["chip_structure_score"] == 50.0  # 未披露的 80 不可用


def _monthly_panel():
    months = pd.date_range("2024-01-31", periods=24, freq="ME")
    stocks = ["A", "B", "C"]
    rows = []
    for s in stocks:
        for m in months:
            rows.append({"stock_code": s, "date": m,
                         "turnover_rate": 2.0 + (m.month % 3) * 0.5,
                         "volume": 1_000_000.0 + (m.month % 4) * 100_000,
                         "amplitude": 5.0 + (m.month % 5)})
    return pd.DataFrame(rows)


def test_cbi_normalization_no_lookahead():
    df1 = _monthly_panel()
    df2 = df1.copy()
    # 修改最后 6 个月数据（极端放大换手）
    df2.loc[df2["date"] >= pd.Timestamp("2025-08-31"), "turnover_rate"] *= 20
    cbi1 = build_cbi(df1, DEFAULT_SETTINGS)
    cbi2 = build_cbi(df2, DEFAULT_SETTINGS)
    past = cbi1["month_end"] < "2025-07-31"
    merged = cbi1[past].merge(cbi2[past][["stock_code", "month_end", "cbi_score"]],
                              on=["stock_code", "month_end"], suffixes=("_1", "_2"))
    cmp = merged.dropna(subset=["cbi_score_1", "cbi_score_2"])
    assert len(cmp) > 0, "应有可比历史 CBI"
    assert np.allclose(cmp["cbi_score_1"], cmp["cbi_score_2"], atol=1e-9), \
        "修改未来数据不得改变历史 CBI"


def test_portfolio_accounting_equal_weight():
    # A +10%、B -10%（零成本）→ 等权组合周收益 = 0%
    settings = copy.deepcopy(DEFAULT_SETTINGS)
    settings["backtest"]["cost"] = {"commission_rate": 0.0, "stamp_rate": 0.0,
                                    "slippage_rate": 0.0, "levy_rate": 0.0}
    signals = pd.DataFrame({
        "stock_code": ["A", "B", "A", "B"],
        "decision_date": ["2026-01-09", "2026-01-09", "2026-01-16", "2026-01-16"],
        "action_signal": ["BUY", "BUY", "HOLD", "HOLD"],
        "mtf_regime": ["BULLISH_CONFIRMED"] * 4,
        "market_regime": ["risk_on"] * 4,
        "structural_regime": ["STRUCTURAL_BULLISH"] * 4,
    })
    weekly = pd.DataFrame({
        "stock_code": ["A", "B", "A", "B"],
        "date": pd.to_datetime(["2026-01-02", "2026-01-02", "2026-01-09", "2026-01-09"]),
        "close": [100.0, 100.0, 110.0, 90.0],
    })
    bt = run_backtest(signals, weekly, settings)
    port = portfolio_returns(bt)
    # 第 1 周仓位 0 → 组合 0；第 2 周 A +10%、B -10% → 组合 0%
    week2 = port[port["week_end"] == "2026-01-09"].iloc[0]
    assert abs(week2["portfolio_return"]) < 1e-12


def test_cost_direction():
    assert buy_rate(DEFAULT_SETTINGS) == 0.0035
    assert abs(sell_rate(DEFAULT_SETTINGS) - 0.00477) < 1e-9
    assert buy_rate(DEFAULT_SETTINGS) < sell_rate(DEFAULT_SETTINGS)


def test_calibration_weight_normalized():
    settings = copy.deepcopy(DEFAULT_SETTINGS)
    settings["fusion"]["chip_confidence"] = {
        "quarterly_chip_weight": 0.5, "cbi_weight": 0.4,
        "high_threshold": 70, "medium_threshold": 50}
    score, _ = compute_chip_confidence(100.0, 0.0, "C↑", settings)
    # 归一化后 w_q = 0.5/0.9 → score = 100 * 0.5/0.9 ≈ 55.56（不再被绝对尺度扭曲）
    assert abs(score - 100 * 0.5 / 0.9) < 1e-4  # score 保留 4 位小数


def test_cross_sectional_time_alignment():
    # T 周选股 → T+1 周收益：
    # 01-09 选出 B（评分 10）→ 01-16 收益应来自 B 当周 0%（而非 A 的 +10%）；
    # 01-16 选出 A（评分 10）→ 01-23 收益应来自 A 的 -9.09%
    settings = copy.deepcopy(DEFAULT_SETTINGS)
    settings["backtest"]["cost"] = {"commission_rate": 0.0, "stamp_rate": 0.0,
                                    "slippage_rate": 0.0, "levy_rate": 0.0}
    signals = pd.DataFrame({
        "stock_code": ["A", "B", "A", "B", "A", "B", "A", "B"],
        "decision_date": ["2026-01-02", "2026-01-02",
                          "2026-01-09", "2026-01-09",
                          "2026-01-16", "2026-01-16",
                          "2026-01-23", "2026-01-23"],
        "score": [10.0, 0.0, 0.0, 10.0, 10.0, 0.0, 10.0, 0.0],
        "target": [1.0] * 8,
    })
    weekly = pd.DataFrame({
        "stock_code": ["A", "A", "A", "A", "B", "B", "B", "B"],
        "date": pd.to_datetime(["2026-01-02", "2026-01-09", "2026-01-16", "2026-01-23"] * 2),
        "close": [100.0, 100.0, 110.0, 100.0, 100.0, 100.0, 100.0, 105.0],
    })
    port = cross_sectional_portfolio(signals, weekly, settings, top_n=1,
                                     score_col="score")
    # 01-09：由 01-02 的组合（A）× 01-09 收益 0 → 0
    r1 = port[port["week_end"] == "2026-01-09"].iloc[0]["portfolio_return"]
    assert abs(r1) < 1e-12
    # 01-16：由 01-09 的组合（B）× B 当周收益 0%（无位移时会是 A 的 +10%）
    r2 = port[port["week_end"] == "2026-01-16"].iloc[0]["portfolio_return"]
    assert abs(r2) < 1e-12
    # 01-23：由 01-16 的组合（A）× A 当周收益 -9.09%
    r3 = port[port["week_end"] == "2026-01-23"].iloc[0]["portfolio_return"]
    assert abs(r3 - (100.0 / 110.0 - 1.0)) < 1e-6  # 组合收益保留 8 位小数


def test_pit_latest_rules():
    from QCFP_MTF.common.asof import pit_latest
    df = pd.DataFrame({
        "period_end": ["2026-03-31", "2026-06-30", "2026-09-30"],
        "available_date": ["2026-05-15", "2026-08-14", "2026-11-14"],
        "structural_regime": ["DECLINE", "BULLISH", "ACCUMULATION"],
    })
    # 决策 07-10：Q2（08-14 可得）不可用 → 用 Q1
    r1 = pit_latest(df, "2026-07-10")
    assert r1["structural_regime"] == "DECLINE"
    # 修改"未来"披露日（Q3 延后）不影响 07-10 的结果
    df2 = df.copy()
    df2.loc[2, "available_date"] = "2026-12-01"
    assert pit_latest(df2, "2026-07-10")["structural_regime"] == "DECLINE"
    # 但修改 Q2 的披露日提前到 07-05 → 07-10 应改用 Q2
    df3 = df.copy()
    df3.loc[1, "available_date"] = "2026-07-05"
    assert pit_latest(df3, "2026-07-10")["structural_regime"] == "BULLISH"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_asof 全部通过 ✅")
