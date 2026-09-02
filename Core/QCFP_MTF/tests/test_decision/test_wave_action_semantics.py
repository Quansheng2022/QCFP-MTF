# coding: utf-8
"""Wave Action Semantic Regression Tests（PHASE3-V1.3/V1.4 P0 修复）

覆盖收口计划 T01–T07 与对抗矩阵 A39–A48：
    - Wave authority（OPPORTUNITY）仍在 FSM（LIFECYCLE）之前；
    - 真实 ProposalAction 由 previous_position vs fsm_proposal_target 派生，
      不得用 previous_position 预判成 HOLD；
    - FSM 后只 lookup/apply FSM 前预计算的 immutable Wave policy，
      不重新评估 wave_stage / permission；
    - 禁止 ADD ≠ 强制 EXIT；Wave ≤ FSM proposal；Wave ≤ Permission。
    - V1.4：BLOCK progressive derisk 不得被 Wave 错误升级成 EXIT；
      permission max_target 是“禁止新增风险”的增量上限，不是已有仓位
      绝对归零上限（HOLD/REDUCE/EXIT 分支按 actual action 解释约束）。
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.decision.action_classifier import proposal_action
from QCFP_MTF.decision.engine import DecisionConfig, evaluate


def _row(wave_stage, **kw):
    base = {
        "stock_code": "T_WAS", "decision_date": "2026-09-01",
        "c_state": "C↑", "f_state": "F↑", "p_state": "P↑",
        "prev_f_state": "F↑", "monthly_behavior_state": "Improving",
        "tactical_signal": "Breakout", "daily_state": "DAILY_BREAKOUT",
        "risk_level": "Low", "des_score": 0, "wave_strength": 0.8,
        "chip_stability_confidence": "High", "data_quality": "A",
        "q_position_52w": 0.2, "q_trend_score": 55.0,
        "market_context": "risk_on", "cbi_state": "CBI_STABLE",
        "catalyst_score": 1.0, "wave_stage": wave_stage,
        "wave_id": "W-001",
    }
    base.update(kw)
    return base


def _block_row(wave_stage, **kw):
    """BLOCK 权限 + 高质量信号（避免独立 TQS 门干扰本 P0 断言）。"""
    base = {
        "stock_code": "T_WAS", "decision_date": "2026-09-02",
        "c_state": "C↓", "f_state": "F↓", "p_state": "P↓",
        "prev_f_state": "F↓", "monthly_behavior_state": "Improving",
        "tactical_signal": "Breakout", "daily_state": "DAILY_NEUTRAL",
        "risk_level": "Low", "des_score": 0, "wave_strength": 0.8,
        "chip_stability_confidence": "High", "data_quality": "A",
        "q_position_52w": 0.2, "q_trend_score": 55.0,
        "market_context": "risk_on", "cbi_state": "CBI_STABLE",
        "catalyst_score": 1.0, "wave_stage": wave_stage,
        "wave_id": "W-001",
    }
    base.update(kw)
    return base


# (stage, previous_position, previous_state, 说明)
ADD_SCENARIOS = [
    ("DISCOVERY", 0.10, "TESTING", "T01"),
    ("CONFIRMING", 0.05, "TESTING", "T02"),
    ("MATURE", 0.10, "TESTING", "T03"),
]

SCENARIOS = [
    ("discovery_add", _row("DISCOVERY"), "TESTING", 0.10),
    ("confirming_add", _row("CONFIRMING"), "TESTING", 0.05),
    ("mature_add", _row("MATURE"), "TESTING", 0.10),
    ("discovery_hold", _row("DISCOVERY"), "BUILDING", 0.20),
    ("exhausting_reduce",
     _row("EXHAUSTING", risk_level="High"), "HOLDING", 0.30),
    ("exhausting_exit",
     _row("EXHAUSTING", des_score=5), "HOLDING", 0.30),
]


# ---------------------------------------------------------------------------
# T01–T03 — 真实 ADD + Wave 阶段禁止加仓 → No-New-Risk，不得强制 EXIT
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("stage,prev,state,label", ADD_SCENARIOS)
def test_forbidden_add_no_new_risk(stage, prev, state, label):
    """actual ADD + Wave add=False → wave_action=ADD、allowed=False、
    wave_proposal_target <= previous_position、且 target 不被强制归零。"""
    snap = evaluate(_row(stage), state, prev, DEFAULT_SETTINGS)
    assert snap.context["wave"]["action"] == "ADD"
    assert snap.wave_action_allowed is False
    assert snap.wave_proposal_target <= prev + 1e-9
    assert snap.wave_proposal_target > 1e-9      # NO ADD != FORCED EXIT
    assert snap.target_position > 1e-9
    assert snap.wave_proposal_target <= snap.fsm_proposal_target + 1e-9


def test_t01_discovery_add_not_forced_exit():
    snap = evaluate(_row("DISCOVERY"), "TESTING", 0.10, DEFAULT_SETTINGS)
    assert snap.context["wave"]["action"] == "ADD"
    assert snap.wave_action_allowed is False
    assert snap.wave_proposal_target == pytest.approx(0.10, abs=1e-9)
    assert snap.target_position == pytest.approx(0.10, abs=1e-9)


# ---------------------------------------------------------------------------
# T04 — HOLD 必须保持 HOLD（Entry Scale 不得把维持扭曲成 EXIT）
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("stage", ("DISCOVERY", "CONFIRMING", "ACTIVE",
                                   "MATURE", "EXHAUSTING"))
def test_t04_hold_not_distorted_by_entry_scale(stage):
    snap = evaluate(_row(stage), "BUILDING", 0.20, DEFAULT_SETTINGS)
    assert snap.context["wave"]["action"] == "HOLD"
    assert snap.wave_action_allowed is True
    assert snap.wave_proposal_target == pytest.approx(0.20, abs=1e-9)
    assert snap.target_position == pytest.approx(0.20, abs=1e-9)
    assert snap.canonical_action == "HOLD"


# ---------------------------------------------------------------------------
# T05 — REDUCE / EXIT 不被 Entry Scale 破坏
# ---------------------------------------------------------------------------

def test_t05_reduce_not_scaled_by_entry_scale():
    """EXHAUSTING（max_entry_scale=0.0）下 REDUCE 不得被乘成 0/EXIT。"""
    snap = evaluate(_row("EXHAUSTING", risk_level="High"),
                    "HOLDING", 0.30, DEFAULT_SETTINGS)
    assert snap.context["wave"]["action"] == "REDUCE"
    assert snap.wave_action_allowed is True
    assert snap.wave_proposal_target == pytest.approx(0.15, abs=1e-9)
    assert snap.target_position == pytest.approx(0.15, abs=1e-9)
    assert snap.canonical_action == "REDUCE"


def test_t05_exit_preserved():
    snap = evaluate(_row("EXHAUSTING", des_score=5),
                    "HOLDING", 0.30, DEFAULT_SETTINGS)
    assert snap.context["wave"]["action"] == "EXIT"
    assert snap.wave_proposal_target == 0.0
    assert snap.target_position == 0.0
    assert snap.canonical_action == "EXIT"


# ---------------------------------------------------------------------------
# T06 — Snapshot Audit Accuracy
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,row,state,prev", SCENARIOS)
def test_t06_wave_audit_matches_actual_proposal(name, row, state, prev):
    snap = evaluate(dict(row), state, prev, DEFAULT_SETTINGS)
    actual = proposal_action(prev, snap.fsm_proposal_target)
    assert snap.context["wave"]["action"] == actual
    assert snap.wave_proposal_target == pytest.approx(
        snap.context["wave"]["proposed_target"], abs=1e-9)


# ---------------------------------------------------------------------------
# T07 — Wave Authority 仍在 FSM 之前
# ---------------------------------------------------------------------------

def test_t07_wave_authority_before_fsm():
    snap = evaluate(_row("ACTIVE"), "TESTING", 0.10, DEFAULT_SETTINGS)
    path = list(snap.decision_path)
    assert "wave" in path and "fsm" in path
    assert path.index("wave") < path.index("fsm")
    # 引擎内 Wave 矩阵预计算发生在 FSM 前，真实 action 派生发生在 FSM 后
    assert snap.context["wave"]["action"] == \
        proposal_action(snap.previous_position, snap.fsm_proposal_target)


# ---------------------------------------------------------------------------
# 三条永久 Property Invariants
# ---------------------------------------------------------------------------

def test_property_forbidden_add_no_new_risk():
    """actual ADD + Wave add=False → wave_proposal_target <= previous_position。"""
    for stage, prev, state, _label in ADD_SCENARIOS:
        snap = evaluate(_row(stage), state, prev, DEFAULT_SETTINGS)
        if snap.context["wave"]["action"] == "ADD" \
                and not snap.wave_action_allowed:
            assert snap.wave_proposal_target <= prev + 1e-9


def test_property_wave_not_above_fsm_proposal():
    for _name, row, state, prev in SCENARIOS:
        snap = evaluate(dict(row), state, prev, DEFAULT_SETTINGS)
        assert snap.wave_proposal_target <= snap.fsm_proposal_target + 1e-9


def test_property_wave_not_above_permission():
    """STRONG_ALLOW permission max_target = 0.70；Wave 不得抬高权限上限。"""
    for _name, row, state, prev in SCENARIOS:
        snap = evaluate(dict(row), state, prev, DEFAULT_SETTINGS)
        assert snap.institutional_permission == "STRONG_ALLOW"
        assert snap.wave_proposal_target <= 0.70 + 1e-9


# ---------------------------------------------------------------------------
# 对抗矩阵 A39–A44
# ---------------------------------------------------------------------------

def test_a39_discovery_add_must_not_force_exit():
    snap = evaluate(_row("DISCOVERY"), "TESTING", 0.10, DEFAULT_SETTINGS)
    assert snap.context["wave"]["action"] == "ADD"
    assert snap.wave_action_allowed is False
    assert snap.target_position > 1e-9     # No-New-Risk，not forced exit


def test_a40_confirming_add_must_not_raise_risk():
    snap = evaluate(_row("CONFIRMING"), "TESTING", 0.05, DEFAULT_SETTINGS)
    assert snap.context["wave"]["action"] == "ADD"
    assert snap.wave_proposal_target <= 0.05 + 1e-9


def test_a41_mature_add_blocked():
    snap = evaluate(_row("MATURE"), "TESTING", 0.10, DEFAULT_SETTINGS)
    assert snap.context["wave"]["action"] == "ADD"
    assert snap.wave_action_allowed is False


def test_a42_fake_hold_audit_rejected():
    """actual ADD 不得在审计里被记成 HOLD。"""
    snap = evaluate(_row("DISCOVERY"), "TESTING", 0.10, DEFAULT_SETTINGS)
    assert snap.context["wave"]["action"] == "ADD"
    assert snap.context["wave"]["action"] != "HOLD"


def test_a43_wave_above_fsm_proposal_rejected():
    for _name, row, state, prev in SCENARIOS:
        snap = evaluate(dict(row), state, prev, DEFAULT_SETTINGS)
        assert snap.wave_proposal_target <= snap.fsm_proposal_target + 1e-9


def test_a44_wave_above_permission_rejected():
    for _name, row, state, prev in SCENARIOS:
        snap = evaluate(dict(row), state, prev, DEFAULT_SETTINGS)
        assert snap.wave_proposal_target <= 0.70 + 1e-9


# ---------------------------------------------------------------------------
# V1.4 — BLOCK Progressive Derisk Preservation（T01–T07）
# ---------------------------------------------------------------------------

def test_t01_block_active_reduce_progressive():
    """BLOCK + existing + ACTIVE Wave + no HardExit → REDUCE 保持渐进（>0）。"""
    snap = evaluate(_block_row("ACTIVE"), "HOLDING", 0.30, DEFAULT_SETTINGS)
    assert snap.institutional_permission == "BLOCK"
    assert snap.exit_event_kind == "NONE"
    assert snap.context["wave"]["action"] == "REDUCE"
    assert 0.0 < snap.wave_proposal_target < 0.30
    assert snap.wave_proposal_target == pytest.approx(0.15, abs=1e-9)
    assert snap.target_position == pytest.approx(0.15, abs=1e-9)
    assert snap.canonical_action == "REDUCE"
    assert snap.next_fsm_state == "TRIMMING"


def test_t02_block_discovery_reduce_progressive():
    """BLOCK + existing + DISCOVERY（弱 Wave）也不得把 REDUCE 直接归零。"""
    snap = evaluate(_block_row("DISCOVERY"), "HOLDING", 0.30,
                    DEFAULT_SETTINGS)
    assert snap.institutional_permission == "BLOCK"
    assert snap.exit_event_kind == "NONE"
    assert snap.context["wave"]["action"] == "REDUCE"
    assert snap.wave_proposal_target == pytest.approx(0.15, abs=1e-9)
    assert snap.target_position == pytest.approx(0.15, abs=1e-9)
    assert snap.canonical_action == "REDUCE"


def test_t03_block_hard_exit_immediate():
    """BLOCK + HardExit 仍必须立即归零（Kill Switch 不被削弱）。"""
    snap = evaluate(_block_row("ACTIVE", des_score=8), "HOLDING", 0.30,
                    DEFAULT_SETTINGS)
    assert snap.exit_event_kind == "HARD_EXIT"
    assert snap.target_position == 0.0
    assert snap.canonical_action == "EXIT"


def test_t04_block_flat_cannot_enter():
    """BLOCK + FLAT：渐进语义不得放行新仓。"""
    snap = evaluate(_block_row("ACTIVE"), "FLAT", 0.0, DEFAULT_SETTINGS)
    assert snap.target_position == 0.0
    assert snap.canonical_action == "NO_TRADE"


def test_t05_watch_existing_hold_preserved():
    """WATCH + existing：维持语义不被 V1.4 波及（No-New-Risk 且不强制退出）。"""
    snap = evaluate(_row("ACTIVE"), "BUILDING", 0.25, DEFAULT_SETTINGS,
                    config=DecisionConfig(override_permission="WATCH"))
    assert snap.institutional_permission == "WATCH"
    assert snap.context["wave"]["action"] == "HOLD"
    assert snap.wave_proposal_target == pytest.approx(0.25, abs=1e-9)
    assert snap.target_position == pytest.approx(0.25, abs=1e-9)
    assert snap.canonical_action == "HOLD"


def test_t06_strong_allow_reduce_control():
    """STRONG_ALLOW + REDUCE 控制组：Action 语义正确，不依赖 BLOCK 特例。"""
    snap = evaluate(_row("ACTIVE", risk_level="High"), "HOLDING", 0.30,
                    DEFAULT_SETTINGS)
    assert snap.institutional_permission == "STRONG_ALLOW"
    assert snap.context["wave"]["action"] == "REDUCE"
    assert snap.wave_proposal_target == pytest.approx(0.15, abs=1e-9)
    assert snap.target_position == pytest.approx(0.15, abs=1e-9)
    assert snap.canonical_action == "REDUCE"


def test_t07_block_reduce_audit_consistent():
    """P0 场景 audit：wave action=REDUCE、无退出事件、三档目标单调。"""
    snap = evaluate(_block_row("ACTIVE"), "HOLDING", 0.30, DEFAULT_SETTINGS)
    assert snap.context["wave"]["action"] == "REDUCE"
    assert snap.canonical_action != "EXIT"
    assert snap.exit_event_kind == "NONE"
    assert snap.wave_proposal_target == pytest.approx(
        snap.context["wave"]["proposed_target"], abs=1e-9)
    assert snap.wave_proposal_target <= snap.fsm_proposal_target + 1e-9
    assert snap.target_position <= snap.wave_proposal_target + 1e-9


# ---------------------------------------------------------------------------
# V1.4 — 对抗矩阵 A45–A48
# ---------------------------------------------------------------------------

def test_a45_block_progressive_reduce_preserved():
    """BLOCK + existing + Wave + no HardExit → progressive REDUCE，非 EXIT。"""
    for stage in ("ACTIVE", "DISCOVERY", "CONFIRMING", "MATURE",
                  "EXHAUSTING", "INVALID"):
        snap = evaluate(_block_row(stage), "HOLDING", 0.30, DEFAULT_SETTINGS)
        assert snap.exit_event_kind == "NONE"
        assert snap.context["wave"]["action"] == "REDUCE"
        assert snap.target_position > 0
        assert snap.target_position < 0.30
        assert snap.canonical_action != "EXIT"


def test_a46_block_hard_exit_still_immediate_exit():
    """BLOCK + existing + HardExit → 立即 EXIT（未削弱 Kill Switch）。"""
    snap = evaluate(_block_row("ACTIVE", des_score=8), "HOLDING", 0.30,
                    DEFAULT_SETTINGS)
    assert snap.exit_event_kind == "HARD_EXIT"
    assert snap.target_position == 0.0
    assert snap.canonical_action == "EXIT"


def test_a47_block_flat_bullish_wave_target_zero():
    """BLOCK + FLAT + bullish Wave → target=0（不得允许新仓）。"""
    snap = evaluate(_block_row("ACTIVE"), "FLAT", 0.0, DEFAULT_SETTINGS)
    assert snap.target_position == 0.0


def test_a48_wave_cannot_convert_reduce_to_exit():
    """actual REDUCE + fsm>0 + 无 Immediate Exit Authority → WaveTarget > 0。"""
    for stage in ("ACTIVE", "DISCOVERY", "CONFIRMING", "MATURE",
                  "EXHAUSTING", "INVALID"):
        snap = evaluate(_block_row(stage), "HOLDING", 0.30, DEFAULT_SETTINGS)
        assert snap.exit_event_kind == "NONE"
        assert snap.context["wave"]["action"] == "REDUCE"
        assert snap.fsm_proposal_target > 0
        assert snap.wave_proposal_target > 0
        assert snap.canonical_action != "EXIT"


# ---------------------------------------------------------------------------
# V1.4 — 三条核心 Property Invariants（INV-01/02 沿用，INV-03 为本 P0 证明）
# ---------------------------------------------------------------------------

def test_inv01_wave_target_not_above_fsm_proposal():
    for stage in ("ACTIVE", "DISCOVERY", "CONFIRMING", "MATURE",
                  "EXHAUSTING", "INVALID"):
        snap = evaluate(_block_row(stage), "HOLDING", 0.30, DEFAULT_SETTINGS)
        assert snap.wave_proposal_target <= snap.fsm_proposal_target + 1e-9


def test_inv02_forbidden_add_no_new_risk():
    for stage, prev, state, _label in ADD_SCENARIOS:
        snap = evaluate(_row(stage), state, prev, DEFAULT_SETTINGS)
        if snap.context["wave"]["action"] == "ADD" \
                and not snap.wave_action_allowed:
            assert snap.wave_proposal_target <= prev + 1e-9


def test_inv03_block_reduce_keeps_positive_wave_target():
    """BLOCK + existing + no HardExit + actual REDUCE + fsm>0
    → WaveTarget > 0（progressive derisk 不被 Wave 归零）。"""
    for stage in ("ACTIVE", "DISCOVERY", "CONFIRMING", "MATURE",
                  "EXHAUSTING", "INVALID"):
        snap = evaluate(_block_row(stage), "HOLDING", 0.30, DEFAULT_SETTINGS)
        assert snap.institutional_permission == "BLOCK"
        assert snap.exit_event_kind == "NONE"
        assert snap.context["wave"]["action"] == "REDUCE"
        assert snap.fsm_proposal_target > 0
        assert snap.wave_proposal_target > 0
