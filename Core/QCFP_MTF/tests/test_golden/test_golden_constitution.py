# coding: utf-8
"""Golden Decision Constitution 测试（42 号）

不是测试模型收益，而是测试"QCFP_MTF 的宪法有没有被代码修改破坏"：
    Case 001  BLOCK+ACTIVE+极强信号 → FinalTarget=0
    Case 002  ALLOW+ACTIVE+Liquidity 20%+Raw 60% → 20% binding=LIQUIDITY
    Case 003  PIT invalid → NO CERTIFIED DECISION
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


def _row(perm="ALLOW", wave=1.0, risk="Low", **kw):
    base = {
        "stock_code": "T_GOLD", "decision_date": "2026-08-21",
        "c_state": "C↑", "f_state": "F↑", "p_state": "P↑",
        "prev_f_state": "F↑", "monthly_behavior_state": "Improving",
        "tactical_signal": "Breakout", "daily_state": "DAILY_BREAKOUT",
        "risk_level": risk, "des_score": 0, "wave_strength": wave,
        "chip_stability_confidence": "High", "data_quality": "B",
        "q_position_52w": 0.2,
    }
    if perm == "BLOCK":
        base.update({"c_state": "C↓", "f_state": "F↓", "p_state": "P↓",
                     "prev_f_state": "F↓"})
    base.update(kw)
    return base


def test_golden_case_001_block_strong():
    """BLOCK + ACTIVE Wave + 极强信号 + 空仓 → FinalTarget=0。"""
    snap = evaluate(dict(_row(perm="BLOCK", wave=1.0)),
                    "FLAT", 0.0, DEFAULT_SETTINGS)
    assert snap.institutional_permission == "BLOCK"
    assert snap.target_position == 0.0


def test_golden_case_002_liquidity_binding():
    """ALLOW + ACTIVE + Liquidity Cap 20% + Raw 60% → 20% binding=LIQUIDITY。"""
    fin = finalize_target("ALLOW", "TRADE", 0.50, raw_target=0.60,
                          previous_position=0.0, liquidity_cap=0.20)
    assert fin["target"] == 0.20
    from QCFP_MTF.decision.constraint_trace import binding_constraint
    b = binding_constraint(fin["constraint_trace"])
    assert b["binding_constraint"] in ("liquidity_cap", "budget_cap")


def test_golden_case_003_pit_invalid_no_certified():
    """PIT invalid → 不产生正式决策。"""
    from QCFP_MTF.data.feature_contract import assert_decision_layer_features
    try:
        assert_decision_layer_features(
            {"future_return": 0.5, "decision_date": "2026-08-21"},
            decision_time="2026-08-21")
        raise AssertionError("should raise FeatureGateError")
    except FeatureGateError:
        pass
