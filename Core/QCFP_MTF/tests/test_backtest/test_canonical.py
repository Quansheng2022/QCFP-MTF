# coding: utf-8
"""2.5 回测同源：canonical_replay 由唯一决策引擎产生 target"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.backtest.canonical import canonical_replay
from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.decision.engine import evaluate


def _signals():
    return pd.DataFrame({
        "stock_code": ["C1", "C1"],
        "decision_date": ["2026-01-09", "2026-01-16"],
        "c_state": ["C↑", "C↑"], "f_state": ["F↑", "F↑"],
        "p_state": ["P↑", "P↑"], "prev_f_state": ["F↑", "F↑"],
        "monthly_behavior_state": ["Improving", "Improving"],
        "tactical_signal": ["Breakout", "Breakout"],
        "risk_level": ["Medium", "Medium"], "des_score": [1, 1],
        "chip_stability_confidence": ["High", "High"],
        "data_quality": ["B", "B"], "q_position_52w": [0.3, 0.3],
        "q_trend_score": [55.0, 55.0], "market_context": ["neutral", "neutral"],
        "cbi_state": ["CBI_STABLE", "CBI_STABLE"],
        "catalyst_score": [1.0, 1.0],
        "structural_available_date": ["2025-11-14", "2025-11-14"],
    })


def test_canonical_replay_matches_engine():
    sig = _signals()
    daily = pd.DataFrame({
        "stock_code": ["C1", "C1"],
        "trade_date": ["2026-01-09", "2026-01-16"],
        "daily_state": ["DAILY_BREAKOUT", "DAILY_BREAKOUT"],
    })
    out = canonical_replay(sig, DEFAULT_SETTINGS, run_id="test_canonical",
                           daily=daily)
    assert "engine_source" in out.columns
    assert (out["engine_source"] == "canonical").all()
    # 与手动有状态重放一致（同一引擎）
    r0 = dict(sig.iloc[0]); r0["daily_state"] = "DAILY_BREAKOUT"
    s1 = evaluate(r0, "FLAT", 0.0, DEFAULT_SETTINGS)
    assert abs(out.iloc[0]["target"] - s1.target_position) < 1e-9
    assert out.iloc[0]["fsm_state"] == s1.next_fsm_state
    r1 = dict(sig.iloc[1]); r1["daily_state"] = "DAILY_BREAKOUT"
    s2 = evaluate(r1, s1.next_fsm_state,
                  s1.target_position, DEFAULT_SETTINGS)
    assert abs(out.iloc[1]["target"] - s2.target_position) < 1e-9


def test_retail_utility_score():
    from QCFP_MTF.backtest.retail_utility import (false_participation_rate,
                                                  retail_utility_score)
    u = retail_utility_score(0.05, 0.2, 0.3, 1.5, 0.1, 2.0)
    cap_eff = 0.05 / 0.2
    expected = (0.40 * 0.05 + 0.20 * cap_eff + 0.15 * 0.3
                + 0.10 * 1.5 - 0.10 * 0.1 - 0.05 * 2.0)
    assert abs(u["retail_utility_score"] - round(expected, 6)) < 1e-9
    assert abs(u["capital_efficiency"] - cap_eff) < 1e-9
    # 错误参与率：参与但亏损的波段占比
    m = pd.DataFrame({"participated": [True, True, False],
                      "strategy_return": [0.05, -0.02, None]})
    assert false_participation_rate(m) == 0.5


def test_portfolio_constraints():
    """组合层暴露约束：单股≤30%、行业≤50%、总暴露≤100%"""
    from QCFP_MTF.backtest.portfolio_constraints import apply_target_constraints
    sig = pd.DataFrame({
        "stock_code": ["A", "B", "C"],
        "decision_date": ["2026-01-09"] * 3,
        "target": [0.9, 0.7, 0.8],
    })
    cfg = {"backtest": {"portfolio_constraints": {
        "enabled": True, "max_single_stock": 0.30,
        "max_sector": 0.50, "max_total_exposure": 1.0}}}
    out = apply_target_constraints(
        sig, cfg, sector_map={"A": "X", "B": "X", "C": "Y"})
    assert out["target"].max() <= 0.30 + 1e-9
    assert out.loc[out["stock_code"].isin(["A", "B"]),
                   "target"].sum() <= 0.50 + 1e-9
    assert out["target"].sum() <= 1.0 + 1e-9


def test_execution_cost_multiplier():
    """Execution Ablation：成本倍数放大费率"""
    import copy
    from QCFP_MTF.backtest.cost_model import directional_cost
    s_base = copy.deepcopy(DEFAULT_SETTINGS)
    s_x3 = copy.deepcopy(DEFAULT_SETTINGS)
    c = s_x3["backtest"]["cost"]
    for k in ("commission_rate", "stamp_rate", "slippage_rate"):
        c[k] = float(c[k]) * 3
    delta = pd.Series([0.0, 0.2])
    base_cost = directional_cost(delta, s_base)
    x3_cost = directional_cost(delta, s_x3)
    assert x3_cost.iloc[1] > base_cost.iloc[1] * 2.5


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_canonical 全部通过 ✅")
