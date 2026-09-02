# coding: utf-8
"""2.6 Execution Simulator 与 Shadow Drift 监控测试"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.execution.simulator import (SCENARIOS, apply_scenario,
                                          fill_ratio, max_order_size)
from QCFP_MTF.shadow.drift import distribution_drift


def test_scenarios_scale_costs_and_fill():
    s = apply_scenario(DEFAULT_SETTINGS, "BASE")
    e = apply_scenario(DEFAULT_SETTINGS, "EXTREME")
    base_slip = s["backtest"]["cost"]["slippage_rate"]
    ext_slip = e["backtest"]["cost"]["slippage_rate"]
    assert ext_slip > base_slip * 5
    assert SCENARIOS["EXTREME"]["fill_rate"] < SCENARIOS["BASE"]["fill_rate"]
    assert s is not DEFAULT_SETTINGS   # 不改原对象


def test_liquidity_and_fill():
    assert max_order_size(1_000_000, 0.10) == 100_000.0
    assert fill_ratio(50_000, 1_000_000, 0.10, 1.0) == 1.0
    # 订单超容量 → 部分成交
    assert fill_ratio(500_000, 1_000_000, 0.10, 1.0) == 0.2
    # 情景成交率再打折
    assert fill_ratio(50_000, 1_000_000, 0.10, 0.5) == 0.5


def test_drift_detection():
    baseline = {"WATCH": 0.30, "TEST": 0.25, "ALLOW": 0.35,
                "STRONG_ALLOW": 0.10}
    live = {"WATCH": 0.75, "TEST": 0.20, "ALLOW": 0.05}
    flag, worst, deltas = distribution_drift(baseline, live, threshold=0.15)
    assert flag is True
    assert worst > 0.15
    assert deltas["WATCH"] == 0.45
    assert "ALLOW" in deltas and deltas["ALLOW"] == 0.30


def test_false_exit_and_whipsaw():
    from QCFP_MTF.backtest.retail_utility import (false_exit_rate,
                                                  whipsaw_rate)
    w = pd.DataFrame({
        "stock_code": ["S"] * 8,
        "date": pd.date_range("2024-01-05", periods=8, freq="W-FRI"),
        "close": [10, 10, 11, 12, 13, 14, 15, 16],
    })
    bt = pd.DataFrame({
        "stock_code": ["S"] * 8,
        "week_end": pd.date_range(
            "2024-01-05", periods=8, freq="W-FRI").strftime("%Y-%m-%d"),
        "position_start": [0, 0, 1, 1, 1, 0, 0, 0],
        "position": [0, 0, 1, 1, 0, 0, 0, 0],
    })
    assert false_exit_rate(bt, w, lookback=2, gain_threshold=0.05) == 1.0
    assert whipsaw_rate(bt, lookback=2) == 0.0          # 持有 3 周，非噪声
    bt2 = bt.copy()
    bt2["position_start"] = [0, 0, 1, 0, 0, 0, 0, 0]   # 进 1 周即退
    bt2["position"] = [0, 0, 1, 0, 0, 0, 0, 0]
    assert whipsaw_rate(bt2, lookback=4) == 1.0


def test_state_forward_stats():
    from QCFP_MTF.scripts.state_validation import forward_stats
    states = pd.DataFrame({
        "stock_code": ["S"], "period_end": ["2024-01-31"],
        "available_date": ["2024-01-05"],
        "institutional_state": ["ACCUMULATION"],
    })
    closes = [10.0 * (1.02 ** i) for i in range(16)]
    w = pd.DataFrame({
        "stock_code": ["S"] * 16,
        "date": pd.date_range("2024-01-12", periods=16, freq="W-FRI"),
        "close": closes,
    })
    s = forward_stats(states, w)
    assert "fwd4w" in s
    acc = s["fwd4w"]["ACCUMULATION"]
    assert acc["n"] >= 1
    assert acc["mean_return"] > 0
    assert "win_rate" in acc


def test_trade_ledger_builds_trades():
    from QCFP_MTF.backtest.trade_ledger import (build_trade_ledger,
                                                trade_ledger_summary)
    w = pd.DataFrame({
        "stock_code": ["S"] * 8,
        "date": pd.date_range("2024-01-05", periods=8, freq="W-FRI"),
        "close": [10, 10, 11, 12, 13, 14, 15, 16],
        "high": [11, 11, 12, 13, 14, 15, 16, 17],
        "low": [9, 9, 10, 11, 12, 13, 14, 15],
    })
    bt = pd.DataFrame({
        "stock_code": ["S"] * 8,
        "week_end": pd.date_range(
            "2024-01-05", periods=8, freq="W-FRI").strftime("%Y-%m-%d"),
        "position_start": [0, 0, 1, 1, 1, 0, 0, 0],
        "position": [0, 0, 1, 1, 1, 0, 0, 0],
        "pnl": [0, 0, 0.1, 0.1, 0.1, 0, 0, 0],
    })
    trades = build_trade_ledger(bt, w)
    assert len(trades) == 1
    t = trades.iloc[0]
    assert t["holding_weeks"] == 2
    assert t["add_count"] == 0
    assert t["mfe"] > 0 and t["mae"] < 0
    s = trade_ledger_summary(trades)
    assert s["n_trades"] == 1
    assert s["avg_holding_weeks"] == 2.0


def test_marginal_utility_matrix():
    from QCFP_MTF.ablation.marginal import marginal_utility_matrix
    models = []
    for name, ret, mdd, cap, to in (
            ("A0_Legacy", 0.01, -0.20, 0.05, 3.0),
            ("A2_FSM", 0.03, -0.10, 0.10, 1.0),
            ("A3_FSM_SoftExit", 0.02, -0.05, 0.08, 0.9),
            ("A4_FSM_HardExit", 0.015, -0.005, 0.09, 0.3),
            ("A5_PermFSM", 0.02, -0.03, 0.08, 0.5),
            ("A8_PermFSM_FullExit", 0.01, -0.002, 0.03, 0.1),
            ("A9_FullNoDaily", 0.0, 0.0, 0.0, 0.0),
            ("A10_FullNoBudget", 0.0, 0.0, 0.0, 0.0),
            ("A13_FullNoObservation", 0.0, 0.0, 0.0, 0.0)):
        models.append({"model": name, "annualized_return": ret,
                       "max_drawdown": mdd, "wave_capture_ratio": cap,
                       "annual_turnover": to})
    m = marginal_utility_matrix({"models": models})
    assert m["permission"]["class"] == "governance"
    assert abs(m["fsm"]["return_delta"] - 0.02) < 1e-9
    assert "capture_delta" in m["hard_exit"]


def _mini_signals():
    return pd.DataFrame({
        "stock_code": ["C1", "C1"],
        "decision_date": ["2026-01-09", "2026-01-16"],
        "action_signal": ["BUY", "BUY"],
        "mtf_regime": ["BULLISH_CONFIRMED", "BULLISH_CONFIRMED"],
        "structural_regime": ["STRUCTURAL_BULLISH", "STRUCTURAL_BULLISH"],
        "c_state": ["C↑", "C↑"], "f_state": ["F↑", "F↑"],
        "p_state": ["P↑", "P↑"], "prev_f_state": ["F↑", "F↑"],
        "monthly_behavior_state": ["Improving", "Improving"],
        "tactical_signal": ["Breakout", "Breakout"],
        "risk_level": ["Medium", "Medium"], "des_score": [1, 1],
        "chip_stability_confidence": ["High", "High"],
        "data_quality": ["B", "B"], "q_position_52w": [0.3, 0.3],
        "q_trend_score": [55.0, 55.0],
        "market_context": ["neutral", "neutral"],
        "cbi_state": ["CBI_STABLE", "CBI_STABLE"],
        "catalyst_score": [1.0, 1.0],
        "structural_available_date": ["2025-11-14", "2025-11-14"],
    })


def _mini_weekly():
    return pd.DataFrame({
        "stock_code": ["C1"] * 4,
        "date": pd.to_datetime(["2026-01-09", "2026-01-16",
                                "2026-01-23", "2026-01-30"]),
        "close": [100.0, 102.0, 104.0, 106.0],
        "high": [101, 103, 105, 107], "low": [99, 101, 103, 105],
    })


def test_permutation_and_timeshift_ablation():
    from QCFP_MTF.ablation.experiments import (permutation_ablation,
                                               time_shift_leakage)
    sig = _mini_signals()
    w = _mini_weekly()
    daily = pd.DataFrame({"stock_code": ["C1", "C1"],
                          "trade_date": ["2026-01-09", "2026-01-16"],
                          "daily_state": ["DAILY_BREAKOUT"] * 2})
    p = permutation_ablation(sig, w, DEFAULT_SETTINGS, daily=daily,
                             seed=1, n_perm=1)
    assert "baseline" in p and "permuted" in p
    t = time_shift_leakage(sig, w, DEFAULT_SETTINGS, daily=daily,
                           shift_weeks=1)
    assert "baseline_annualized" in t and "shifted_annualized" in t


def test_portfolio_governance_risk_budget_and_cash():
    from QCFP_MTF.backtest.portfolio_constraints import \
        apply_portfolio_governance
    sig = pd.DataFrame({
        "stock_code": ["A", "B", "C"],
        "decision_date": ["2026-01-09"] * 3,
        "target": [0.9, 0.7, 0.8],
    })
    cfg = {"backtest": {"portfolio_constraints": {
        "enabled": True, "max_single_stock": 0.30, "max_sector": 0.50,
        "max_total_exposure": 1.0, "min_cash": 0.10,
        "total_risk_budget": 0.06, "high_corr_cap": 0.30}}}
    out = apply_portfolio_governance(
        sig, cfg, sector_map={"A": "X", "B": "X", "C": "Y"})
    assert out["target"].sum() <= 0.90 + 1e-9          # 现金储备 ≥10%
    from QCFP_MTF.decision.stop_loss import stop_loss_buffer_pct
    stop = stop_loss_buffer_pct(DEFAULT_SETTINGS)
    assert (out["target"] * stop).sum() <= 0.06 + 1e-9  # 总风险预算
    assert out.loc[out["stock_code"].isin(["A", "B"]),
                   "target"].sum() <= 0.30 + 1e-9      # 高相关上限


def test_drift_report_multidim():
    from QCFP_MTF.shadow.drift import drift_report
    baseline = {"permission_dist": {"WATCH": 0.3, "ALLOW": 0.7},
                "setup_dist": {"BREAKOUT": 0.5, "NONE": 0.5},
                "avg_holding": 4.0}
    live = {"permission_dist": {"WATCH": 0.9, "ALLOW": 0.1},
            "setup_dist": {"BREAKOUT": 0.5, "NONE": 0.5},
            "avg_holding": 4.0}
    d = drift_report(baseline, live, thresholds={"distribution": 0.15})
    assert "permission_dist" in d["drifted"]
    assert d["overall"] == "WARNING"
    live2 = {**live, "avg_holding": 1.0}
    d2 = drift_report(baseline, live2, thresholds={
        "distribution": 0.15, "avg_holding": 1.5})
    assert d2["overall"] == "RESEARCH_REVIEW"


def test_complexity_budget():
    from QCFP_MTF.governance.complexity_budget import complexity_budget
    models = []
    for name, ret, mdd, cap, to in (
            ("A0_Legacy", 0.01, -0.20, 0.05, 3.0),
            ("A2_FSM", 0.03, -0.10, 0.10, 1.0),
            ("A3_FSM_SoftExit", 0.02, -0.05, 0.08, 0.9),
            ("A4_FSM_HardExit", 0.015, -0.005, 0.09, 0.3),
            ("A5_PermFSM", 0.02, -0.03, 0.08, 0.5),
            ("A8_PermFSM_FullExit", 0.01, -0.002, 0.03, 0.1),
            ("A9_FullNoDaily", 0.01, -0.002, 0.03, 0.1),
            ("A10_FullNoBudget", 0.01, -0.002, 0.03, 0.1),
            ("A13_FullNoObservation", 0.01, -0.002, 0.03, 0.1)):
        models.append({"model": name, "annualized_return": ret,
                       "max_drawdown": mdd, "wave_capture_ratio": cap,
                       "annual_turnover": to})
    b = complexity_budget({"models": models})
    assert b["verdicts"]["fsm"] == "KEEP"
    assert "permission" in b["verdicts"]
    assert 0 <= b["complexity_score"] <= 1


def test_benchmark_targets_built():
    from QCFP_MTF.backtest.benchmarks import benchmark_targets
    sig = _mini_signals()
    w = _mini_weekly()
    bench = benchmark_targets(sig, w, DEFAULT_SETTINGS)
    for name in ("B0_BuyHold", "B2_SimpleTrend", "B3_Breakout",
                 "B4_WaveOnly", "B5_PermissionOnly", "B6_PermissionWave"):
        assert name in bench
    assert (bench["B0_BuyHold"]["target"] == 1.0).all()
    assert bench["B5_PermissionOnly"]["target"].between(0, 0.7).all()


def test_failure_mode_database():
    from QCFP_MTF.failure.failure_modes import (FailureModeDB,
                                                classify_failure, classify_miss)
    assert "F05" in classify_failure(
        {"net_return": -0.1, "mae": -0.05, "entry_late": True,
         "exit_early": False, "whipsaw": False})
    assert classify_failure({"net_return": 0.05, "entry_late": False,
                             "exit_early": True, "whipsaw": False}) == ["F07"]
    assert classify_miss("PERMISSION_BLOCK") == "F01"
    assert classify_miss("SETUP_ABSENT") == "F03"
    db = FailureModeDB()
    db.record("F01", stock="S", regime="HighVolatility", cost=-0.2)
    db.record(["F05", "F07"], stock="S", regime="HighVolatility", cost=-0.1)
    s = db.summary()
    assert s["by_code"]["F01"] == 1 and s["by_code"]["F05"] == 1
    assert s["by_regime"]["HighVolatility"] == 3


def test_cost_scenarios_c0_c3():
    from QCFP_MTF.execution.simulator import SCENARIO_ALIASES, SCENARIOS
    assert SCENARIO_ALIASES["c0"] == "C0_LOW"
    assert SCENARIO_ALIASES["c3"] == "EXTREME"
    assert SCENARIOS["C0_LOW"]["slippage"] < SCENARIOS["EXTREME"]["slippage"]
    s = apply_scenario(DEFAULT_SETTINGS, "C0_LOW")
    assert s["backtest"]["cost"]["commission_rate"] < \
        DEFAULT_SETTINGS["backtest"]["cost"]["commission_rate"]


def test_capacity_model():
    from QCFP_MTF.execution.capacity import (capacity_assessment,
                                             exit_stress_days, market_impact,
                                             participation_rate)
    impact = market_impact(5_000_000, 30_000_000, participation=0.10)
    assert 0.0 < impact < 0.05
    assert participation_rate(3_000_000, 30_000_000) == 0.1
    assert exit_stress_days(3_000_000, 30_000_000, 0.10) == 1
    assert exit_stress_days(30_000_000, 30_000_000, 0.10) == 10
    a = capacity_assessment(30_000_000, 30_000_000, 0.3, participation=0.02)
    assert "SLOW_EXIT" in a["flags"]


def test_fsm_transition_matrix():
    from QCFP_MTF.fsm.transition_matrix import (build_transition_matrix,
                                                expected_state_value,
                                                transition_matrix_by)
    seq = ["FLAT", "TESTING", "TESTING", "BUILDING", "HOLDING",
           "HOLDING", "TRIMMING", "EXITING", "COOLDOWN", "FLAT"]
    m = build_transition_matrix(seq)
    assert abs(sum(m["TESTING"].values()) - 1.0) < 1e-9
    assert m["HOLDING"].get("TRIMMING", 0) > 0
    import pandas as pd
    df = pd.DataFrame({"decision_date": range(len(seq)),
                       "next_fsm_state": seq,
                       "institutional_permission": ["ALLOW"] * len(seq)})
    by = transition_matrix_by(df)
    assert "('ALLOW',)" in by
    ev = expected_state_value(m, {"HOLDING": 1.0, "BUILDING": 0.5})
    assert "FLAT" in ev


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_execution_simulator 全部通过 ✅")
