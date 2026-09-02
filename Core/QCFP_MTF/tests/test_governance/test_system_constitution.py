# coding: utf-8
"""System Constitution Test（80 号：核心宪法不可回归测试）

任何版本只要违反任一条宪法，就算收益提升也不能 Promotion。
这里同时测试宪法检查器本身，并把宪法直接接线到真实代码行为。
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.data.feature_contract import assert_decision_layer_features
from QCFP_MTF.data.information_set import PITViolation
from QCFP_MTF.decision.abstain import abstain_decision
from QCFP_MTF.decision.engine import evaluate
from QCFP_MTF.decision.governance import finalize_target
from QCFP_MTF.decision.schema_contract import snapshot_replayability
from QCFP_MTF.governance.feature_gate import FeatureGateError
from QCFP_MTF.governance.system_constitution import CONSTITUTION_PRINCIPLES, \
    system_constitution_check


def _row(perm="ALLOW", wave=1.0):
    base = {
        "stock_code": "T_CONST", "decision_date": "2026-08-21",
        "c_state": "C↑", "f_state": "F↑", "p_state": "P↑",
        "prev_f_state": "F↑", "monthly_behavior_state": "Improving",
        "tactical_signal": "Breakout", "daily_state": "DAILY_BREAKOUT",
        "risk_level": "Low", "des_score": 0, "wave_strength": wave,
        "chip_stability_confidence": "High", "data_quality": "B",
        "q_position_52w": 0.2,
    }
    if perm == "BLOCK":
        base.update({"c_state": "C↓", "f_state": "F↓", "p_state": "P↓",
                     "prev_f_state": "F↓"})
    return base


def _valid_fields():
    return {
        "decision_id": "d1", "stock_code": "01951",
        "decision_date": "2026-08-21",
        "institutional_permission": "ALLOW", "target_position": 0.2,
        "wave_stage": "ACTIVE", "binding_constraint": "portfolio_cap",
        "release_id": "REL-1", "release_manifest_hash": "MH1",
        "decision_path_hash": "PH1", "canonical_action": "ENTRY",
        "wave_proposal_target": 0.15,
        "previous_position": 0.0, "raw_target_position": 0.25,
        "next_fsm_state": "TESTING", "primary_reason": "WAVE_CONFIRM",
        "context": {},
    }


def test_constitution_checker_all_pass():
    checks = {k: True for k, _ in CONSTITUTION_PRINCIPLES}
    r = system_constitution_check(checks)
    assert r["pass"] is True
    assert r["promotion_verdict"] == "PROMOTE_OK"


def test_constitution_violation_rejects_promotion():
    checks = {k: True for k, _ in CONSTITUTION_PRINCIPLES}
    checks["NO_FUTURE_IN_PAST"] = (False, "发现未来特征")
    r = system_constitution_check(checks)
    assert r["pass"] is False
    assert r["promotion_verdict"] == "PROMOTION_REJECTED"
    assert "NO_FUTURE_IN_PAST" in r["failures"]


def test_constitution_permission_over_signal():
    """BLOCK + 极强 Wave 信号 → target=0（Permission > Signal）。"""
    snap = evaluate(dict(_row(perm="BLOCK", wave=1.0)),
                    "FLAT", 0.0, DEFAULT_SETTINGS)
    assert snap.institutional_permission == "BLOCK"
    assert snap.target_position == 0.0


def test_constitution_pit_over_prediction():
    """Evaluation-only 未来标签不能进入 Decision（PIT > Prediction）。"""
    try:
        assert_decision_layer_features(
            {"future_return": 0.5, "decision_date": "2026-08-21"},
            decision_time="2026-08-21")
        raise AssertionError("should raise FeatureGateError")
    except FeatureGateError:
        pass


def test_constitution_no_future_in_past():
    """available_date 晚于决策时间 → 禁止进入（future 不能进入过去）。"""
    try:
        assert_decision_layer_features(
            {"decision_date": "2026-08-21",
             "structural_available_date": "2026-09-01"},
            decision_time="2026-08-21")
        raise AssertionError("should raise PITViolation")
    except (FeatureGateError, PITViolation):
        pass


def test_constitution_target_only_downstream_reduction():
    """Final Target 只能在下游被压减，不能大于 raw_target。"""
    fin = finalize_target("ALLOW", "TRADE", 0.50, raw_target=0.60,
                          previous_position=0.0, liquidity_cap=0.20)
    assert fin["target"] <= 0.60


def test_constitution_unknown_must_degrade():
    """PIT UNKNOWN → NO_DECISION（Unknown 必须降级）。"""
    r = abstain_decision(pit_ok=False)
    assert r["decision"] == "NO_DECISION"


def test_constitution_every_decision_replayable():
    """合法 Snapshot 必须可直接 Replay。"""
    r = snapshot_replayability("DECISION-1.1", _valid_fields())
    assert r["verdict"] == "REPLAY"


def test_constitution_risk_over_return():
    """治理失败时，收益再高也不能通过生产验收。"""
    from QCFP_MTF.governance.production_acceptance import \
        PRODUCTION_ACCEPTANCE_GATES, production_acceptance_contract
    gates = {g: {"ok": True, "evidence": "ok"} for g in
             PRODUCTION_ACCEPTANCE_GATES}
    gates["OOS"] = {"ok": True, "evidence": "Sharpe=3.0"}
    gates["GOVERNANCE"] = {"ok": False, "evidence": "越权"}
    r = production_acceptance_contract(gates)
    assert r["verdict"] == "REJECTED"
