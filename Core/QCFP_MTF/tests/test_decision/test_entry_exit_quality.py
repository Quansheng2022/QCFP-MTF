# coding: utf-8
"""Entry / Exit Quality Engine 测试（14/15 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.entry_quality import (entry_quality_gate,
                                             evaluate_entry_quality)
from QCFP_MTF.decision.exit_quality import evaluate_exit_quality
from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.decision.action_gate import evaluate_action
from QCFP_MTF.decision.engine import DecisionConfig, evaluate


def test_entry_quality_high():
    eq = evaluate_entry_quality(
        price_position_52w=0.1, confirmation=0.9, volume_confirmation=0.8,
        weekly_volatility=0.05, invalidation_distance=0.04,
        expected_mfe=0.30, expected_mae=0.06, execution_cost=0.004)
    assert eq.band == "HIGH"
    assert eq.score >= 70


def test_entry_quality_low():
    eq = evaluate_entry_quality(
        price_position_52w=0.95, confirmation=0.2, volume_confirmation=0.2,
        weekly_volatility=0.20, invalidation_distance=0.18,
        expected_mfe=0.05, expected_mae=0.25, execution_cost=0.025)
    assert eq.band == "LOW"


def test_entry_quality_gate_strong_wave_low_entry():
    eq = evaluate_entry_quality(
        price_position_52w=0.95, confirmation=0.2, volume_confirmation=0.2,
        weekly_volatility=0.20, invalidation_distance=0.18,
        expected_mfe=0.05, expected_mae=0.25, execution_cost=0.025)
    allowed, reason = entry_quality_gate(0.8, eq)
    assert allowed is False
    assert "STRONG_WAVE_LOW_ENTRY" in reason


def test_entry_quality_gate_ok():
    eq = evaluate_entry_quality(
        price_position_52w=0.1, confirmation=0.9, volume_confirmation=0.8,
        weekly_volatility=0.05, invalidation_distance=0.04,
        expected_mfe=0.30, expected_mae=0.06, execution_cost=0.004)
    allowed, _ = entry_quality_gate(0.8, eq)
    assert allowed is True


def test_exit_quality_hard_priority():
    eq = evaluate_exit_quality(hard_exit=True, profit_take_hit=True,
                               signal_weakened=True)
    assert eq.kind == "HARD"
    assert eq.suggested_action == "EXIT"
    assert eq.severity == 3


def test_exit_quality_priority_order():
    # GOVERNANCE > REGIME > TIME > SIGNAL > RISK > PROFIT
    eq = evaluate_exit_quality(portfolio_risk_off=True, regime_crisis=True,
                               time_exit=True)
    assert eq.kind == "GOVERNANCE"
    eq = evaluate_exit_quality(regime_crisis=True, time_exit=True,
                               signal_weakened=True)
    assert eq.kind == "REGIME"
    eq = evaluate_exit_quality(time_exit=True, signal_weakened=True,
                               stop_loss_hit=True)
    assert eq.kind == "TIME"
    eq = evaluate_exit_quality(signal_weakened=True, stop_loss_hit=True)
    assert eq.kind == "SIGNAL"
    eq = evaluate_exit_quality(stop_loss_hit=True, trailing_stop_hit=True)
    assert eq.kind == "RISK"
    eq = evaluate_exit_quality(trailing_stop_hit=True)
    assert eq.kind == "PROFIT"
    eq = evaluate_exit_quality()
    assert eq.kind == "NONE"
    assert eq.suggested_action == "HOLD"


def _row(**kw):
    base = {
        "stock_code": "T_EQ", "decision_date": "2026-08-21",
        "c_state": "C↑", "f_state": "F↑", "p_state": "P↑",
        "prev_f_state": "F↑", "monthly_behavior_state": "Improving",
        "tactical_signal": "Breakout", "daily_state": "DAILY_BREAKOUT",
        "risk_level": "Low", "des_score": 1,
        "chip_stability_confidence": "High", "data_quality": "B",
        "q_position_52w": 0.3, "wave_strength": 0.8,
    }
    base.update(kw)
    return base


def test_action_gate_entry_quality_wait():
    eq = evaluate_entry_quality(
        price_position_52w=0.95, confirmation=0.2, volume_confirmation=0.2,
        weekly_volatility=0.20, invalidation_distance=0.18,
        expected_mfe=0.05, expected_mae=0.25, execution_cost=0.025)
    action, reasons = evaluate_action(
        "ALLOW", "FLAT", "BREAKOUT", "Low", 0.0, 0.5,
        entry_quality=eq, wave_strength=0.8)
    assert action == "WAIT"
    assert any("LOW_ENTRY" in r for r in reasons)


def test_action_gate_no_entry_quality_compat():
    action, _ = evaluate_action("ALLOW", "FLAT", "BREAKOUT", "Low", 0.0, 0.5)
    assert action == "ENTRY"


def test_engine_entry_quality_gate_off_by_default():
    row = _row()
    snap = evaluate(dict(row), "FLAT", 0.0, DEFAULT_SETTINGS)
    assert snap.context["quality"]["entry_quality"] is None
    assert snap.context["quality"]["exit_quality"]["kind"] == "NONE"


def test_engine_entry_quality_gate_on_high_52w():
    row = _row(q_position_52w=0.95, wave_strength=0.8)
    default = evaluate(dict(row), "FLAT", 0.0, DEFAULT_SETTINGS)
    gated = evaluate(dict(row), "FLAT", 0.0, DEFAULT_SETTINGS,
                     config=DecisionConfig(use_entry_quality=True))
    # 默认配置无进场质量门：强波+高位仍按 2.7 行为给出 ADD
    assert default.context["action"] == "ADD"
    assert gated.context["quality"]["entry_quality"] is not None
    assert gated.context["quality"]["entry_quality"]["band"] == "LOW"
    # 进场质量门在"强波+高位"下把 ENTRY 压成 WAIT
    assert gated.context["action"] == "WAIT"
    assert any("STRONG_WAVE_LOW_ENTRY" in r
               for r in gated.context["action_reasons"])


def test_entry_quality_timing_bands():
    # INVALID：波已耗尽或 90% MFE 已实现
    eq = evaluate_entry_quality(wave_stage="EXHAUSTING", realized_mfe_ratio=0.95)
    assert eq.timing_band == "INVALID"
    # LATE：MATURE 或 52W 高位
    eq = evaluate_entry_quality(wave_stage="MATURE")
    assert eq.timing_band == "LATE"
    eq = evaluate_entry_quality(price_position_52w=0.9)
    assert eq.timing_band == "LATE"
    # EARLY：CONFIRMING / 弱趋势
    eq = evaluate_entry_quality(wave_stage="CONFIRMING")
    assert eq.timing_band == "EARLY"
    eq = evaluate_entry_quality(trend_score=30)
    assert eq.timing_band == "EARLY"
    # OPTIMAL：ACTIVE + 回撤介入 + 位置不偏高
    eq = evaluate_entry_quality(wave_stage="ACTIVE", pullback=True,
                                price_position_52w=0.3)
    assert eq.timing_band == "OPTIMAL"
    # 默认
    eq = evaluate_entry_quality()
    assert eq.timing_band == "ACCEPTABLE"


def test_exit_quality_wave_and_liquidity_kinds():
    eq = evaluate_exit_quality(wave_exhausted=True, signal_weakened=True)
    assert eq.kind == "WAVE"
    assert eq.suggested_action == "REDUCE"
    eq = evaluate_exit_quality(liquidity_low=True, time_exit=True)
    assert eq.kind == "LIQUIDITY"
    # 优先级：REGIME > LIQUIDITY > TIME > WAVE
    eq = evaluate_exit_quality(regime_crisis=True, liquidity_low=True,
                               time_exit=True, wave_exhausted=True)
    assert eq.kind == "REGIME"
