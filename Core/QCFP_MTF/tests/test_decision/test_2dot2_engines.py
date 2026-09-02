# coding: utf-8
"""QCFP-MTF 2.2 正式引擎测试（hard_exit / swing_setup / position sizing / 集成）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.decision.hard_exit import ExitEvent, evaluate_exit_events, \
    evaluate_hard_exit
from QCFP_MTF.decision.decision_snapshot import (build_decision_snapshot,
                                                 build_report_snapshot)
from QCFP_MTF.decision.retail_position_fsm import (PERMISSION_FSM_MATRIX,
                                                   RetailDecisionContext,
                                                   TransitionInput,
                                                   assert_permission_bound,
                                                   assert_no_risk_increase,
                                                   build_fsm_timeline, next_state,
                                                   permission_cap_exceeded,
                                                   permission_risk_increase_allowed,
                                                   transition)
from QCFP_MTF.decision.retail_position_sizing import retail_target_position
from QCFP_MTF.setup.swing_setup import evaluate_swing_setup


def test_hard_exit():
    assert evaluate_hard_exit(des_score=8, settings=DEFAULT_SETTINGS)[0] is True
    assert evaluate_hard_exit(risk_level="Extreme", settings=DEFAULT_SETTINGS)[0] is True
    assert evaluate_hard_exit(stop_triggered=True, settings=DEFAULT_SETTINGS)[0] is True
    # 周线破位 + 有持仓 → Hard Exit；空仓 → 不触发
    assert evaluate_hard_exit(weekly_signal="Breakdown", current_position=0.3,
                              settings=DEFAULT_SETTINGS)[0] is True
    assert evaluate_hard_exit(weekly_signal="Breakdown", current_position=0.0,
                              settings=DEFAULT_SETTINGS)[0] is False
    assert evaluate_hard_exit(des_score=3, weekly_signal="Consolidation",
                              settings=DEFAULT_SETTINGS)[0] is False


def test_swing_setup():
    assert evaluate_swing_setup("Breakout", "DAILY_BREAKOUT") == "BREAKOUT"
    assert evaluate_swing_setup("Pullback", "DAILY_PULLBACK") == "PULLBACK"
    assert evaluate_swing_setup("Consolidation", "DAILY_ACCUMULATION") == "ACCUMULATION"
    assert evaluate_swing_setup("Breakout", "DAILY_NEUTRAL", permission="TEST") == "RECOVERY"
    assert evaluate_swing_setup("Consolidation", "DAILY_NEUTRAL") == "NONE"


def test_position_sizing_additive():
    assert retail_target_position("TESTING", 0.0, DEFAULT_SETTINGS) == 0.10
    assert retail_target_position("BUILDING", 0.20, DEFAULT_SETTINGS) == 0.30
    assert retail_target_position("HOLDING", 0.40, DEFAULT_SETTINGS) == 0.40
    assert retail_target_position("TRIMMING", 0.40, DEFAULT_SETTINGS) == 0.25
    assert retail_target_position("EXITING", 0.40, DEFAULT_SETTINGS) == 0.0
    # 加法不超过上限（不乘法加仓）
    assert retail_target_position("BUILDING", 0.65, DEFAULT_SETTINGS) == 0.70


def test_integration_cases():
    # Case 1：BLOCK + DAILY_BREAKOUT + Low + FLAT → FLAT
    c = RetailDecisionContext(institutional_permission="BLOCK",
                              daily_state="DAILY_BREAKOUT", risk_level="Low", des_score=1)
    assert next_state("FLAT", c) == "FLAT"
    # Case 2：TEST + PULLBACK + Medium + 0 → TESTING
    c = RetailDecisionContext(institutional_permission="TEST",
                              weekly_signal="Pullback", daily_state="DAILY_PULLBACK",
                              risk_level="Medium", des_score=1)
    assert next_state("FLAT", c) == "TESTING"
    # Case 3：ALLOW + BREAKOUT + 10% → BUILDING
    c = RetailDecisionContext(institutional_permission="ALLOW",
                              weekly_signal="Breakout", daily_state="DAILY_BREAKOUT",
                              risk_level="Medium", des_score=1, current_position=0.10)
    assert next_state("TESTING", c) == "BUILDING"
    # Case 4：STRONG_ALLOW + BREAKOUT + DES=8 → EXITING（Hard Exit 最高优先级）
    c = RetailDecisionContext(institutional_permission="STRONG_ALLOW",
                              weekly_signal="Breakout", daily_state="DAILY_BREAKOUT",
                              risk_level="Low", des_score=8, current_position=0.30)
    assert next_state("HOLDING", c) == "EXITING"


def test_permission_downgrade_trims_holding():
    # HOLDING + Permission 降级到 BLOCK（周线仍看多/日线中性/DES 低）→ TRIMMING（不是 EXIT）
    c = RetailDecisionContext(institutional_permission="BLOCK",
                              weekly_signal="Consolidation",
                              daily_state="DAILY_NEUTRAL", risk_level="Medium",
                              des_score=3, current_position=0.40)
    assert next_state("HOLDING", c) == "TRIMMING"
    assert next_state("BUILDING", c) == "TRIMMING"
    # WATCH + High/Distribution → TRIMMING；WATCH + 正常 → HOLDING
    c2 = RetailDecisionContext(institutional_permission="WATCH",
                               weekly_signal="Consolidation",
                               daily_state="DAILY_NEUTRAL", risk_level="Low",
                               des_score=2, current_position=0.40)
    assert next_state("HOLDING", c2) == "HOLDING"
    c3 = RetailDecisionContext(institutional_permission="WATCH",
                               weekly_signal="Consolidation",
                               daily_state="DAILY_DISTRIBUTION", risk_level="Medium",
                               des_score=2, current_position=0.40)
    assert next_state("HOLDING", c3) == "TRIMMING"


def test_no_bypass_matrix():
    # 任何普通 Bullish/Breakout 都不能绕过 BLOCK 或 Hard Exit
    for trigger in ("Breakout", "Pullback", "Consolidation"):
        for risk in ("Low", "Medium", "High"):
            c = RetailDecisionContext(
                institutional_permission="BLOCK", weekly_signal=trigger,
                daily_state="DAILY_BREAKOUT", risk_level=risk, des_score=1)
            assert next_state("FLAT", c) == "FLAT"
    for des in (7, 8):
        c = RetailDecisionContext(
            institutional_permission="STRONG_ALLOW",
            weekly_signal="Breakout", daily_state="DAILY_BREAKOUT",
            risk_level="Low", des_score=des, current_position=0.30)
        assert next_state("HOLDING", c) == "EXITING"


def test_permission_fsm_matrix_exhaustive():
    # 穷举 Permission × FSM 状态矩阵（正常风险/中性日线下，结果必须等于冻结矩阵；
    # EXITING/COOLDOWN 为 Lifecycle 覆盖，独立断言）
    for perm, row in PERMISSION_FSM_MATRIX.items():
        for cur, expected in row.items():
            if cur in ("EXITING", "COOLDOWN"):
                continue   # 生命周期状态由 Lifecycle Override 接管（见下）
            escalate = expected in ("TESTING", "BUILDING") and cur in ("FLAT", "TESTING")
            c = RetailDecisionContext(
                institutional_permission=perm,
                weekly_signal="Breakout" if escalate else "Consolidation",
                daily_state="DAILY_BREAKOUT" if escalate else "DAILY_NEUTRAL",
                risk_level="Medium", des_score=1,
                current_position=0.3 if cur != "FLAT" else 0.0)
            got = next_state(cur, c)
            assert got == expected, f"{perm}×{cur}: expect {expected}, got {got}"
    # Lifecycle Override：EXITING → COOLDOWN；COOLDOWN（冷却未完）→ COOLDOWN
    for perm in PERMISSION_FSM_MATRIX:
        c_ex = RetailDecisionContext(institutional_permission=perm,
                                     risk_level="Medium", des_score=1,
                                     current_position=0.3)
        assert next_state("EXITING", c_ex) == "COOLDOWN"
        c_cd = RetailDecisionContext(institutional_permission=perm,
                                     risk_level="Medium", des_score=1,
                                     cooldown_remaining=1)
        assert next_state("COOLDOWN", c_cd) == "COOLDOWN"


def test_full_state_matrix_coverage():
    """5 Permissions × 7 FSM States 全部有明确 Base Policy"""
    from QCFP_MTF.decision.retail_position_fsm import STATES
    for perm, row in PERMISSION_FSM_MATRIX.items():
        assert set(row) == set(STATES), f"{perm} 缺矩阵列"
        for cur, base in row.items():
            assert base in STATES, f"{perm}×{cur}: 非法基准 {base}"


def test_matrix_is_base_transition():
    """矩阵即基准源：无事件/无覆盖时 transition == permission_fsm_base"""
    from QCFP_MTF.decision.retail_position_fsm import permission_fsm_base
    for perm, row in PERMISSION_FSM_MATRIX.items():
        for cur, expected in row.items():
            if cur in ("EXITING", "COOLDOWN"):
                continue
            # 提供 Setup 确认（矩阵中 FLAT→TESTING / TESTING→BUILDING 需要确认）
            if cur == "FLAT" and expected == "TESTING":
                setup_type, daily = "BREAKOUT", "DAILY_BREAKOUT"
            elif cur == "TESTING" and expected == "BUILDING":
                setup_type, daily = "PULLBACK", "DAILY_PULLBACK"
            else:
                setup_type, daily = None, "DAILY_NEUTRAL"
            t = TransitionInput(
                permission=perm, exit_event=ExitEvent("NONE"),
                setup_type=setup_type, risk_level="Medium",
                weekly_signal="Consolidation", daily_state=daily,
                monthly_state="Stable", previous_state=cur,
                previous_position=0.3 if cur != "FLAT" else 0.0)
            base = permission_fsm_base(perm, cur)
            assert transition(t) == base == expected, \
                f"{perm}×{cur}: transition={transition(t)} base={base}"


def test_fsm_timeline_cross_stock_isolation():
    allow_a = {"stock_code": "AAA", "institutional_permission": "ALLOW",
               "risk_level": "Medium", "des_score": 1,
               "daily_state": "DAILY_BREAKOUT", "tactical_signal": "Breakout",
               "q_position_52w": 0.3}
    block_b = {**allow_a, "stock_code": "BBB", "institutional_permission": "BLOCK"}
    rows = [allow_a, block_b, allow_a, block_b]
    states = [s for s, _ in build_fsm_timeline(rows, DEFAULT_SETTINGS)]
    assert states == ["TESTING", "FLAT", "BUILDING", "FLAT"]  # 每只股票独立 FLAT 起点


def test_hard_exit_covers_building_holding():
    for st in ("BUILDING", "HOLDING", "TRIMMING"):
        c = RetailDecisionContext(institutional_permission="STRONG_ALLOW",
                                  weekly_signal="Breakout",
                                  daily_state="DAILY_BREAKOUT",
                                  risk_level="Extreme", des_score=3,
                                  current_position=0.3)
        assert next_state(st, c) == "EXITING"
        c2 = RetailDecisionContext(institutional_permission="STRONG_ALLOW",
                                   weekly_signal="Breakout",
                                   daily_state="DAILY_BREAKOUT",
                                   risk_level="Low", des_score=3,
                                   stop_triggered=True, current_position=0.3)
        assert next_state(st, c2) == "EXITING"


def test_exit_event_kinds():
    assert evaluate_exit_events(des_score=8, settings=DEFAULT_SETTINGS).kind == "HARD_EXIT"
    assert evaluate_exit_events(des_score=8, settings=DEFAULT_SETTINGS).hard is True
    assert evaluate_exit_events(risk_level="Extreme",
                                settings=DEFAULT_SETTINGS).kind == "FORCED_DELEVERAGE"
    assert evaluate_exit_events(stop_triggered=True,
                                settings=DEFAULT_SETTINGS).kind == "STOP_EXIT"
    # 软退出：DES 5~6 / 空仓周线破位 —— 仍由 Exit Event 单一来源给出
    assert evaluate_exit_events(des_score=6,
                                settings=DEFAULT_SETTINGS).kind == "RISK_EXIT"
    assert evaluate_exit_events(des_score=6,
                                settings=DEFAULT_SETTINGS).hard is False
    assert evaluate_exit_events(weekly_signal="Breakdown", current_position=0.0,
                                settings=DEFAULT_SETTINGS).kind == "BREAKDOWN"
    assert evaluate_exit_events(weekly_signal="Breakdown", current_position=0.0,
                                settings=DEFAULT_SETTINGS).hard is False
    assert evaluate_exit_events(des_score=1, weekly_signal="Consolidation",
                                settings=DEFAULT_SETTINGS).kind == "NONE"


def test_permission_cap_and_assert():
    assert permission_cap_exceeded("BLOCK", "BUILDING") is True
    assert permission_cap_exceeded("BLOCK", "FLAT") is False
    assert permission_cap_exceeded("BLOCK", "TRIMMING") is False   # 既有仓位降级
    # V31：WATCH 维持既有风险合法（矩阵 WATCH×BUILDING→BUILDING），不再算状态级越权
    assert permission_cap_exceeded("WATCH", "BUILDING") is False
    assert permission_cap_exceeded("ALLOW", "HOLDING") is False
    try:
        assert_permission_bound("BLOCK", "BUILDING")
        raise AssertionError("should raise")
    except PermissionError:
        pass


def test_permission_monotonicity():
    # ALLOW 得到 BUILDING；STRONG_ALLOW 不应反向得到 TESTING
    from QCFP_MTF.decision.retail_position_fsm import PERMISSION_CAP
    assert PERMISSION_CAP["ALLOW"] == "BUILDING"
    assert PERMISSION_CAP["STRONG_ALLOW"] == "HOLDING"
    c = RetailDecisionContext(institutional_permission="ALLOW",
                              weekly_signal="Breakout",
                              daily_state="DAILY_BREAKOUT",
                              risk_level="Medium", des_score=1,
                              current_position=0.3)
    assert next_state("TESTING", c) == "BUILDING"


def test_position_ownership():
    # FSM 只给状态，不直接给数值仓位
    from QCFP_MTF.decision.retail_position_sizing import retail_target_position
    c = RetailDecisionContext(institutional_permission="ALLOW",
                              weekly_signal="Breakout",
                              daily_state="DAILY_BREAKOUT",
                              risk_level="Medium", des_score=1,
                              current_position=0.30)
    assert next_state("TESTING", c) == "BUILDING"
    assert retail_target_position("BUILDING", 0.30, DEFAULT_SETTINGS) == 0.40


def test_decision_snapshot_deterministic():
    row = {"stock_code": "00371", "decision_date": "2026-08-21",
           "c_state": "C↑", "f_state": "F↓", "p_state": "P↓",
           "monthly_behavior_state": "Improving", "tactical_signal": "Breakdown",
           "daily_state": "DAILY_DECLINE", "risk_level": "Extreme",
           "des_score": 12, "chip_stability_confidence": "Medium",
           "data_quality": "C", "q_position_52w": 0.09}
    s1 = build_decision_snapshot("HOLDING", 0.4, row, DEFAULT_SETTINGS)
    s2 = build_decision_snapshot("HOLDING", 0.4, row, DEFAULT_SETTINGS)
    assert s1.as_dict() == s2.as_dict()
    assert s1.exit_event_kind == "HARD_EXIT"     # DES=12 ≥7 优先
    assert s1.next_fsm_state == "EXITING"
    assert s1.target_position == 0.0
    assert s1.permission_cap == "TESTING"        # NEUTRAL→WATCH → cap TESTING


def test_ablation_a3_removes_des_hard_exit():
    """A3 隔离：exit_event=NONE 时，即使 DES≥7 也不得因 Hard Exit 进入 EXITING"""
    # 直接构造 transition：FSM 看不到 DES，只消费 ExitEvent
    t = TransitionInput(permission="STRONG_ALLOW", exit_event=ExitEvent("NONE"),
                        setup_type="BREAKOUT", risk_level="Low",
                        weekly_signal="Breakout", daily_state="DAILY_BREAKOUT",
                        monthly_state="Improving", previous_state="HOLDING",
                        previous_position=0.3)
    assert transition(t) == "HOLDING"
    t_hard = TransitionInput(permission="STRONG_ALLOW",
                             exit_event=ExitEvent("HARD_EXIT", "des_ge_threshold"),
                             setup_type="BREAKOUT", risk_level="Low",
                             weekly_signal="Breakout",
                             daily_state="DAILY_BREAKOUT",
                             monthly_state="Improving", previous_state="HOLDING",
                             previous_position=0.3)
    assert transition(t_hard) == "EXITING"
    # Context 层：预计算 NONE 事件覆盖高 DES（不再从 des_score 重推 Hard Exit）
    c = RetailDecisionContext(institutional_permission="STRONG_ALLOW",
                              weekly_signal="Breakout",
                              daily_state="DAILY_BREAKOUT", risk_level="Low",
                              des_score=8, current_position=0.3,
                              exit_event=ExitEvent("NONE"))
    assert next_state("HOLDING", c) == "HOLDING"
    c2 = RetailDecisionContext(institutional_permission="STRONG_ALLOW",
                               weekly_signal="Breakout",
                               daily_state="DAILY_BREAKOUT", risk_level="Low",
                               des_score=1, current_position=0.3,
                               exit_event=ExitEvent("HARD_EXIT", "des_ge_threshold"))
    assert next_state("HOLDING", c2) == "EXITING"


def test_ablation_exit_filter():
    """Ablation Delta：A2 全关 / A3 仅软 / A4 全开，只有 hard 模块变化"""
    from QCFP_MTF.scripts.permission_fsm_ablation import _filter_exit_event
    ev_hard = ExitEvent("HARD_EXIT", "des_ge_threshold")
    ev_soft = ExitEvent("RISK_EXIT", "des_ge_soft_threshold")
    ev_stop = ExitEvent("STOP_EXIT", "stop_triggered")
    # A2：无退出
    assert _filter_exit_event(ev_hard, False, False).kind == "NONE"
    assert _filter_exit_event(ev_soft, False, False).kind == "NONE"
    # A3：软退出保留，硬退出移除
    assert _filter_exit_event(ev_soft, True, False).kind == "RISK_EXIT"
    assert _filter_exit_event(ev_hard, True, False).kind == "NONE"
    assert _filter_exit_event(ev_stop, True, False).kind == "NONE"
    # A4：全部保留
    assert _filter_exit_event(ev_hard, True, True).kind == "HARD_EXIT"
    assert _filter_exit_event(ev_soft, True, True).kind == "RISK_EXIT"
    assert _filter_exit_event(ev_stop, True, True).kind == "STOP_EXIT"


def test_exit_event_single_source():
    """FSM 只用 ctx.exit_event，不再二次解释 des_score/risk_level"""
    # NONE 事件 + Extreme 风险 → 不因风险等级进入 Hard Exit
    c = RetailDecisionContext(institutional_permission="ALLOW",
                              weekly_signal="Breakout",
                              daily_state="DAILY_BREAKOUT", risk_level="Extreme",
                              des_score=3, current_position=0.3,
                              exit_event=ExitEvent("NONE"))
    assert next_state("BUILDING", c) == "HOLDING"   # 无退出事件 → 正常升级
    # 软退出事件 RISK_EXIT → EXITING（不依赖 des_score 字段）
    c2 = RetailDecisionContext(institutional_permission="ALLOW",
                               weekly_signal="Consolidation",
                               daily_state="DAILY_NEUTRAL", risk_level="Medium",
                               des_score=0, current_position=0.3,
                               exit_event=ExitEvent("RISK_EXIT", "des_ge_soft_threshold"))
    assert next_state("HOLDING", c2) == "EXITING"


def test_permission_risk_increase_invariant():
    """Permission = 风险增量上限：BLOCK/WATCH 下 target 不得高于 previous"""
    for p in ("BLOCK", "WATCH"):
        assert permission_risk_increase_allowed(p, 0.4, 0.4) is True
        assert permission_risk_increase_allowed(p, 0.4, 0.3) is True
        assert permission_risk_increase_allowed(p, 0.4, 0.5) is False
    for p in ("TEST", "ALLOW", "STRONG_ALLOW"):
        assert permission_risk_increase_allowed(p, 0.0, 0.1) is True
    try:
        assert_no_risk_increase("WATCH", 0.4, 0.5)
        raise AssertionError("should raise")
    except PermissionError:
        pass
    # 快照层：WATCH + BUILDING（维持矩阵状态）→ 目标仓位被封顶为 previous
    row = {"stock_code": "T1", "decision_date": "2026-08-21",
           "c_state": "C→", "f_state": "F→", "p_state": "P→",
           "monthly_behavior_state": "Stable", "tactical_signal": "Consolidation",
           "daily_state": "DAILY_NEUTRAL", "risk_level": "Medium",
           "des_score": 2, "chip_stability_confidence": "Medium",
           "data_quality": "B", "q_position_52w": 0.4}
    snap = build_decision_snapshot("BUILDING", 0.3, row, DEFAULT_SETTINGS)
    assert snap.institutional_permission == "WATCH"
    assert snap.next_fsm_state == "BUILDING"        # 矩阵：维持
    assert snap.target_position <= 0.3 + 1e-9        # 不新增风险


def test_report_snapshot_consistency():
    """报告层一致性：散户卡只展示 DecisionSnapshot（无 Shadow 时=单点推算）"""
    from QCFP_MTF.decision.retail import retail_card_lines
    from pathlib import Path as _Path
    row = {"stock_code": "ZZZ", "decision_date": "2099-01-01",
           "c_state": "C↑", "f_state": "F↑", "p_state": "P↑",
           "monthly_behavior_state": "Improving", "tactical_signal": "Breakout",
           "daily_state": "DAILY_BREAKOUT", "risk_level": "Medium",
           "des_score": 1, "chip_stability_confidence": "High",
           "data_quality": "B", "q_position_52w": 0.4,
           "structure_behavior_alignment": "Aligned", "mtf_regime": "BULLISH_CONFIRMED"}
    no_shadow = _Path(__file__).parent / "_no_shadow"
    snap, source = build_report_snapshot(row, DEFAULT_SETTINGS, shadow_dir=no_shadow)
    assert "NON_CANONICAL" in source
    direct = build_decision_snapshot("FLAT", 0.0, row, DEFAULT_SETTINGS)
    assert snap.as_dict() == direct.as_dict()
    card = "\n".join(retail_card_lines(row, DEFAULT_SETTINGS))
    assert snap.next_fsm_state in card
    assert f"{snap.target_position * 100:.0f}%" in card
    assert snap.institutional_permission in card
    # V31：交易阶梯/红黄绿灯也由 Snapshot 派生（报告层零重算）
    from QCFP_MTF.decision.retail import action_from_snapshot, snapshot_light
    assert action_from_snapshot(snap) in card
    assert snapshot_light(snap) in card
    assert snap.institutional_persistence == 0 or True  # 字段存在


def test_state_position_consistency():
    """状态-仓位一致性：0 仓位不得停留在风险承载状态"""
    from QCFP_MTF.decision.retail_position_fsm import state_position_consistent
    assert state_position_consistent("HOLDING", 0.0) == "FLAT"
    assert state_position_consistent("BUILDING", 0.0) == "FLAT"
    assert state_position_consistent("TESTING", 0.0) == "FLAT"
    assert state_position_consistent("TRIMMING", 0.0) == "EXITING"
    assert state_position_consistent("HOLDING", 0.3) == "HOLDING"
    # 快照层：BLOCK 下 TRIMMING(10%) → target 0 → EXITING/FLAT，不返回 HOLDING@0
    row = {"stock_code": "T2", "decision_date": "2026-08-21",
           "c_state": "C↓", "f_state": "F↓", "p_state": "P↓",
           "monthly_behavior_state": "Deteriorating",
           "tactical_signal": "Consolidation", "daily_state": "DAILY_NEUTRAL",
           "risk_level": "Medium", "des_score": 1,
           "chip_stability_confidence": "Medium", "data_quality": "B",
           "q_position_52w": 0.4}
    snap = build_decision_snapshot("TRIMMING", 0.10, row, DEFAULT_SETTINGS)
    assert snap.institutional_permission == "BLOCK"
    assert snap.target_position == 0.0
    assert snap.next_fsm_state not in ("TESTING", "BUILDING", "HOLDING")
    # 通用不变量：target=0 时 FSM 不在风险承载状态
    assert not (snap.target_position == 0.0
                and snap.next_fsm_state in ("TESTING", "BUILDING", "HOLDING"))


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_2dot2_engines 全部通过 ✅")
