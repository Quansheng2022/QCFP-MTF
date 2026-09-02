# coding: utf-8
"""GovernanceCaps 接入 Canonical Engine 测试（新 2 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.decision.engine import evaluate
from QCFP_MTF.decision.governance_caps import GovernanceCaps, \
    assert_target_within_caps, caps_from_row


def _row(**kw):
    base = {
        "stock_code": "T_CAPS", "decision_date": "2026-08-21",
        "c_state": "C↑", "f_state": "F↑", "p_state": "P↑",
        "prev_f_state": "F↑", "monthly_behavior_state": "Improving",
        "tactical_signal": "Breakout", "daily_state": "DAILY_BREAKOUT",
        "risk_level": "Low", "des_score": 0, "wave_strength": 1.0,
        "chip_stability_confidence": "High", "data_quality": "B",
        "q_position_52w": 0.2, "q_trend_score": 55.0,
        "market_context": "risk_on", "cbi_state": "CBI_STABLE",
        "catalyst_score": 1.0,
    }
    base.update(kw)
    return base


def test_caps_from_row():
    caps = caps_from_row({"portfolio_cap": 0.2, "liquidity_cap": 0.5})
    assert caps.portfolio_cap == 0.2
    assert caps.liquidity_cap == 0.5
    assert caps.execution_cap == 1.0


def test_target_within_caps():
    caps = GovernanceCaps(portfolio_cap=0.2, liquidity_cap=0.5)
    assert assert_target_within_caps(0.15, caps)["within_caps"] is True
    r = assert_target_within_caps(0.3, caps)
    assert r["within_caps"] is False
    assert "portfolio_cap" in r["violations"]


def test_nan_cap_fail_closed():
    """MTR Closure（Sprint C）：NaN cap 必须 UNKNOWN → no-new-risk，
    不得被静默放行。"""
    caps = GovernanceCaps(risk_cap=float("nan"))
    r = assert_target_within_caps(0.2, caps)
    assert r["within_caps"] is False
    assert r["unknown_caps"] == ["risk_cap"]
    from QCFP_MTF.decision.governance import finalize_target
    fin = finalize_target(
        "ALLOW", "TRADE", 0.5, raw_target=0.4, previous_position=0.0,
        liquidity_cap=float("nan"), portfolio_cap=0.3)
    assert fin["target"] == 0.0      # prev=0 → NaN cap → no-new-risk


def test_caps_governance_check_nan_missing():
    from QCFP_MTF.decision.governance_caps import caps_governance_check
    r = caps_governance_check(
        {"portfolio_cap": 0.3, "liquidity_cap": float("nan"),
         "execution_cap": 0.5}, mode="production")
    assert r["unknown"] is True
    assert "liquidity_cap" in r["missing_required"]
    assert r["degrade"] == "NO_NEW_RISK"


def test_engine_applies_hard_caps():
    """FinalTarget <= 所有 hard caps，且 binding constraint 可追溯。"""
    snap = evaluate(_row(portfolio_cap=0.05, liquidity_cap=0.5),
                    "FLAT", 0.0, DEFAULT_SETTINGS)
    assert snap.target_position <= 0.05 + 1e-9
    assert snap.binding_constraint == "portfolio_cap"
    assert snap.governance_caps["portfolio_cap"] == 0.05
    assert snap.constraint_trace  # ConstraintTrace 必须存在


def test_engine_liquidity_cap_binds():
    snap = evaluate(_row(portfolio_cap=0.8, liquidity_cap=0.03),
                    "FLAT", 0.0, DEFAULT_SETTINGS)
    assert snap.target_position <= 0.03 + 1e-9
    assert snap.binding_constraint == "liquidity_cap"
