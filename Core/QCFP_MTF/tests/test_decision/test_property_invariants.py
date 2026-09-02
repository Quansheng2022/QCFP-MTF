# coding: utf-8
"""Canonical Governance Property / Invariant Tests（P0-18 号）

不是证明"正常输入能运行"，而是证明"无论信号多强，都无法绕过治理"。
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.decision.engine import evaluate
from QCFP_MTF.decision.governance import finalize_target
from QCFP_MTF.governance.feature_gate import FeatureGateError
from QCFP_MTF.report.contract import assert_report_ledger_only
from QCFP_MTF.wave.canonical import wave_stage_gate


def _row(perm="ALLOW", wave=0.95, risk="Low", daily="DAILY_BREAKOUT",
         des=0, **kw):
    base = {
        "stock_code": "T_PROP", "decision_date": "2026-08-21",
        "c_state": "C↑", "f_state": "F↑", "p_state": "P↑",
        "prev_f_state": "F↑", "monthly_behavior_state": "Improving",
        "tactical_signal": "Breakout", "daily_state": daily,
        "risk_level": risk, "des_score": des, "wave_strength": wave,
        "chip_stability_confidence": "High", "data_quality": "B",
        "q_position_52w": 0.2,
    }
    if perm == "BLOCK":
        base.update({"c_state": "C↓", "f_state": "F↓", "p_state": "P↓",
                     "prev_f_state": "F↓"})
    base.update(kw)
    return base


def test_final_target_leq_all_caps():
    fin = finalize_target("ALLOW", "TRADE", 0.5, raw_target=0.30,
                          previous_position=0.0, risk_budget=0.02,
                          stop_distance=0.10, portfolio_cap=0.08,
                          liquidity_cap=0.05, execution_cap=0.04,
                          drawdown_cap=0.06)
    assert fin["target"] <= 0.04
    assert fin["target"] <= 0.05
    assert fin["target"] <= 0.08
    assert fin["target"] <= 0.06


def test_adversarial_extreme_alpha_block():
    """极端 Alpha + BLOCK + ACTIVE Wave + 组合可用 → 仍不能越权。"""
    snap = evaluate(dict(_row(perm="BLOCK", wave=1.0, risk="Low")),
                    "FLAT", 0.0, DEFAULT_SETTINGS)
    assert snap.institutional_permission == "BLOCK"
    assert snap.target_position == 0.0


def test_mature_no_add_invalid_no_entry():
    assert wave_stage_gate("MATURE", "ADD")["allowed"] is False
    assert wave_stage_gate("INVALID", "ENTRY")["allowed"] is False


def test_daily_signal_cannot_raise_permission():
    weak = evaluate(dict(_row(perm="BLOCK", daily="DAILY_NEUTRAL")),
                    "FLAT", 0.0, DEFAULT_SETTINGS)
    strong = evaluate(dict(_row(perm="BLOCK", daily="DAILY_BREAKOUT")),
                      "FLAT", 0.0, DEFAULT_SETTINGS)
    assert weak.institutional_permission == "BLOCK"
    assert strong.institutional_permission == "BLOCK"


def test_future_label_blocked_from_production():
    try:
        from QCFP_MTF.data.feature_contract import assert_decision_layer_features
        assert_decision_layer_features(
            {"future_return": 0.5, "decision_date": "2026-08-21"},
            decision_time="2026-08-21")
        raise AssertionError("should raise")
    except FeatureGateError:
        pass


def test_report_cannot_change_snapshot():
    snap = evaluate(dict(_row()), "FLAT", 0.0, DEFAULT_SETTINGS)
    ledger = {"institutional_permission": snap.institutional_permission,
              "previous_fsm_state": snap.prev_fsm_state,
              "next_fsm_state": snap.next_fsm_state,
              "final_target": snap.target_position,
              "primary_reason": snap.primary_reason}
    assert_report_ledger_only(snap, ledger)   # 不抛错
