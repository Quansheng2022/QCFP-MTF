# coding: utf-8
"""1–10 收敛工程不变量测试（P0 系统宪法）

I1  BLOCK → 不新增风险（空仓归零；既有仓位逐步去风险 target ≤ previous）
I2  final_target ≤ permission_cap
I3  final_target ≤ risk_cap
I4  portfolio exposure ≤ portfolio_limit
I5  hard_exit → final_target = 0
I10 Permission Monotonicity：Wave ↑ ≠ Permission ↑
另覆盖：Governance Proof 计算 / 目标链 raw→governed→final /
FSM 权威 / InformationSet PIT / Wave 阶段门。
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.data.information_set import InformationSet, PITViolation, \
    build_information_set
from QCFP_MTF.decision.decision_certificate import build_certificate
from QCFP_MTF.decision.decision_snapshot import build_decision_snapshot
from QCFP_MTF.decision.engine import DecisionConfig, evaluate
from QCFP_MTF.decision.fsm_authority import (FSMStateAuthorityError,
                                             assert_fsm_explains_target_change)
from QCFP_MTF.decision.governance import finalize_target
from QCFP_MTF.decision.governance_proof import prove
from QCFP_MTF.decision.permission_gate import (PermissionGateError,
                                               assert_permission_upper_bound,
                                               assert_wave_cannot_upgrade,
                                               permission_cap)
from QCFP_MTF.governance.feature_gate import FeatureGateError
from QCFP_MTF.wave.canonical import wave_stage_gate


def _row(inst="ALLOW", risk="Medium", des=1, **kw):
    base = {
        "stock_code": "T_CONV", "decision_date": "2026-08-21",
        "c_state": "C↑", "f_state": "F↑", "p_state": "P↑",
        "prev_f_state": "F↑", "monthly_behavior_state": "Improving",
        "tactical_signal": "Breakout", "daily_state": "DAILY_BREAKOUT",
        "risk_level": risk, "des_score": des,
        "chip_stability_confidence": "High", "data_quality": "B",
        "q_position_52w": 0.3,
    }
    if inst == "BLOCK":
        base.update({"c_state": "C↓", "f_state": "F↓", "p_state": "P↓",
                     "prev_f_state": "F↓"})
    base.update(kw)
    return base


def test_i1_block_target_zero():
    snap = build_decision_snapshot("HOLDING", 0.3, _row("BLOCK"),
                                   DEFAULT_SETTINGS)
    assert snap.institutional_permission == "BLOCK"
    assert snap.target_position < 0.3          # 既有仓位逐步去风险
    snap0 = build_decision_snapshot("FLAT", 0.0, _row("BLOCK"),
                                    DEFAULT_SETTINGS)
    assert snap0.target_position == 0.0        # 空仓 BLOCK → 0


def test_i2_final_leq_permission_cap():
    snap = build_decision_snapshot("FLAT", 0.0, _row("ALLOW"),
                                   DEFAULT_SETTINGS)
    assert snap.target_position <= permission_cap("ALLOW") + 1e-9
    snap2 = build_decision_snapshot("FLAT", 0.0, _row("TEST"),
                                    DEFAULT_SETTINGS)
    assert snap2.target_position <= permission_cap("TEST") + 1e-9


def test_i3_final_leq_risk_cap():
    fin = finalize_target("ALLOW", "TRADE", 0.5, raw_target=0.3,
                          previous_position=0.0, risk_budget=0.02,
                          stop_distance=0.10)
    proof = fin["proof"]
    assert proof.final_target <= proof.risk_cap + 1e-9


def test_i4_portfolio_exposure_leq_limit():
    fin = finalize_target("ALLOW", "TRADE", 0.5, raw_target=0.3,
                          previous_position=0.0, portfolio_cap=0.08)
    assert fin["target"] <= 0.08 + 1e-9
    assert fin["proof"].portfolio_cap == 0.08


def test_i5_hard_exit_target_zero():
    snap = build_decision_snapshot("HOLDING", 0.4, _row(des=8),
                                   DEFAULT_SETTINGS)
    assert snap.exit_severity >= 3
    assert snap.target_position == 0.0


def test_i10_wave_cannot_upgrade_permission():
    # Wave ↑ 但 Permission 不变 → OK
    assert_wave_cannot_upgrade("TEST", 0.3, "TEST", 0.9)
    # Wave ↑ 导致 Permission ↑ → 抛错
    try:
        assert_wave_cannot_upgrade("TEST", 0.3, "ALLOW", 0.9)
        raise AssertionError("should raise")
    except PermissionGateError:
        pass


def test_permission_gate_upper_bound():
    assert permission_cap("ALLOW") == 0.5
    assert_permission_upper_bound("ALLOW", 0.4)
    try:
        assert_permission_upper_bound("ALLOW", 0.6)
        raise AssertionError("should raise")
    except PermissionGateError:
        pass
    try:
        assert_permission_upper_bound("BLOCK", 0.01)
        raise AssertionError("should raise")
    except PermissionGateError:
        pass


def test_target_chain_raw_governed_final():
    fin = finalize_target("ALLOW", "TRADE", 0.5, raw_target=0.12,
                          previous_position=0.0, risk_budget=0.02,
                          stop_distance=0.10, portfolio_cap=0.04,
                          liquidity_cap=0.03)
    proof = fin["proof"]
    assert proof.raw_target == 0.12
    assert proof.governed_target > 0
    assert proof.final_target == 0.03      # min(0.12, 0.5, 0.2, 0.04, 0.03)
    assert proof.final_target <= proof.portfolio_cap
    assert proof.final_target <= proof.liquidity_cap


def test_governance_passed_computed_not_forged():
    snap = build_decision_snapshot("FLAT", 0.0, _row("ALLOW"),
                                   DEFAULT_SETTINGS)
    cert = build_certificate(snap)
    assert cert.governance_passed is True
    # 违规输入 → prove FAIL（引擎不得输出 Decision）
    bad = prove("BLOCK", "TRADE", 0.0, 0.0, 0.5, 0.1, 0.1, 0.0)
    assert bad.proof == "FAIL"
    assert "BLOCK_TARGET_NONZERO" in bad.violations


def test_fsm_authority_validator():
    assert_fsm_explains_target_change("FLAT", "TESTING", 0.0, 0.05)
    assert_fsm_explains_target_change("TESTING", "BUILDING", 0.05, 0.10)
    try:
        assert_fsm_explains_target_change("HOLDING", "HOLDING", 0.05, 0.10)
        raise AssertionError("should raise")
    except FSMStateAuthorityError:
        pass
    try:
        assert_fsm_explains_target_change("FLAT", "TESTING", 0.0, 0.0)
        raise AssertionError("0 仓位不得停留在 TESTING")
    except FSMStateAuthorityError:
        pass


def test_information_set_pit():
    ev = {"c_state": "C↑", "f_state": "F↑", "p_state": "P↑",
          "q_position_52w": 0.3, "data_quality": "B",
          "decision_date": "2026-08-21"}
    info = build_information_set(ev, "2026-08-21")
    assert isinstance(info, InformationSet)
    info.assert_pit_clean()
    # 未来特征 → FeatureGateError
    bad = dict(ev, future_return=0.5)
    try:
        build_information_set(bad, "2026-08-21")
        raise AssertionError("should raise FeatureGateError")
    except FeatureGateError:
        pass
    # available_at > decision_time → PITViolation
    ev2 = dict(ev, structural_available_date="2026-09-01")
    try:
        build_information_set(ev2, "2026-08-21")
        raise AssertionError("should raise PITViolation")
    except PITViolation:
        pass


def test_engine_feature_contract_gate():
    # 默认开启契约门：未来特征进入 Decision → Abort
    row = _row(future_return=0.5)
    try:
        evaluate(dict(row), "FLAT", 0.0, DEFAULT_SETTINGS)
        raise AssertionError("should raise FeatureGateError")
    except FeatureGateError:
        pass
    # 关闭门 → 原行为（供 Ablation 对比）
    snap = evaluate(dict(row), "FLAT", 0.0, DEFAULT_SETTINGS,
                    config=DecisionConfig(use_feature_contracts=False))
    assert snap.target_position >= 0


def test_wave_stage_gate():
    assert wave_stage_gate("ACTIVE", "ENTRY")["allowed"] is True
    assert wave_stage_gate("MATURE", "ADD")["allowed"] is False
    assert wave_stage_gate("EXHAUSTING", "ENTRY")["allowed"] is False
    assert wave_stage_gate("INVALID", "HOLD")["allowed"] is False
    assert wave_stage_gate("CONFIRMING", "ENTRY")["max_entry_scale"] == 0.5
