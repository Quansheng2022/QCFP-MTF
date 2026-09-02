# coding: utf-8
"""2.3 Decision Invariants（系统级硬不变量，永不失败的契约测试）

审查建议的 10 条不变量：
   1) BLOCK   → final_target <= previous_position
   2) WATCH   → final_target <= previous_position
   3) Daily   → permission_after == permission_before（Daily 不能升级权限）
   4) HardExit → final_target == 0
   5) PIT-invalid → research_valid == False
   6) position == 0 → FSM ∉ {TESTING, BUILDING, HOLDING}
   7) decision_date < available_date → impossible（Look-ahead 断言）
   8) Report.action == DecisionSnapshot.action
   9) Backtest.target == DecisionLedger.final_target（同引擎重放）
  10) Shadow.target == Backtest.target（重放确定性）
"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.backtest.lookahead_filter import assert_no_lookahead
from QCFP_MTF.backtest.run_status import run_status
from QCFP_MTF.common.db import connect
from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.decision.decision_ledger import load_ledger_snapshot, \
    record_snapshot
from QCFP_MTF.decision.decision_snapshot import (build_decision_snapshot,
                                                 build_report_snapshot)
from QCFP_MTF.decision.retail import action_from_snapshot, retail_card_lines


def _row(inst="WATCH", stock="T_INV", daily="DAILY_NEUTRAL",
         des=1, risk="Medium", pos=0.0, prev_f="F→", **kw):
    base = {
        "stock_code": stock,
        "decision_date": "2026-08-21",
        "c_state": "C→", "f_state": "F→", "p_state": "P→",
        "prev_f_state": prev_f,
        "monthly_behavior_state": "Stable",
        "tactical_signal": "Consolidation",
        "daily_state": daily,
        "risk_level": risk,
        "des_score": des,
        "chip_stability_confidence": "High",
        "data_quality": "B",
        "q_position_52w": 0.4,
    }
    if inst == "BLOCK":
        base.update({"c_state": "C↓", "f_state": "F↓", "p_state": "P↓",
                     "prev_f_state": "F↓"})
    elif inst == "WATCH":
        base.update({"c_state": "C→", "f_state": "F→", "p_state": "P→"})
    elif inst in ("ALLOW", "STRONG_ALLOW"):
        base.update({"c_state": "C↑", "f_state": "F↑", "p_state": "P↑",
                     "prev_f_state": "F↑"})
    base.update(kw)
    return base


def test_invariant_1_2_no_risk_increase():
    for inst, exp_perm in (("BLOCK", "BLOCK"), ("WATCH", "WATCH")):
        snap = build_decision_snapshot("HOLDING", 0.3, _row(inst), DEFAULT_SETTINGS)
        assert snap.institutional_permission == exp_perm
        assert snap.target_position <= 0.3 + 1e-9


def test_invariant_3_daily_cannot_upgrade_permission():
    sa = build_decision_snapshot("FLAT", 0.0,
                                 _row("BLOCK", daily="DAILY_BREAKOUT"),
                                 DEFAULT_SETTINGS)
    sb = build_decision_snapshot("FLAT", 0.0,
                                 _row("BLOCK", daily="DAILY_NEUTRAL"),
                                 DEFAULT_SETTINGS)
    assert sa.institutional_permission == sb.institutional_permission == "BLOCK"


def test_invariant_4_hard_exit_target_zero():
    snap = build_decision_snapshot("HOLDING", 0.4,
                                   _row("ALLOW", des=8), DEFAULT_SETTINGS)
    assert snap.exit_event_kind == "HARD_EXIT"
    assert snap.target_position == 0.0


def test_invariant_5_pit_invalid_not_research_valid():
    # PIT-C（估算披露）不允许 research_validation 模式
    st = run_status({"backtest": {"mode": "research_validation"}}, False)
    assert st["status"] == "FAILED"
    # PIT-invalid 数据（available_date > decision_date）→ 回测 Look-ahead 断言
    bad = pd.DataFrame({
        "stock_code": ["X"], "decision_date": ["2026-08-21"],
        "structural_available_date": ["2026-09-01"]})
    try:
        assert_no_lookahead(bad)
        raise AssertionError("should raise")
    except ValueError:
        pass


def test_invariant_6_zero_position_no_risk_state():
    for state in ("TESTING", "BUILDING", "HOLDING"):
        snap = build_decision_snapshot(state, 0.0, _row("ALLOW"),
                                       DEFAULT_SETTINGS)
        assert not (snap.target_position == 0.0
                    and snap.next_fsm_state in ("TESTING", "BUILDING", "HOLDING"))


def test_invariant_7_decision_before_available_impossible():
    bad = pd.DataFrame({
        "stock_code": ["X"], "decision_date": ["2026-08-20"],
        "structural_available_date": ["2026-08-21"]})
    try:
        assert_no_lookahead(bad)
        raise AssertionError("should raise")
    except ValueError:
        pass


def test_invariant_8_report_action_equals_snapshot():
    row = _row("ALLOW", stock="T_INV8")
    snap, _ = build_report_snapshot(
        row, DEFAULT_SETTINGS,
        shadow_dir=Path(__file__).parent / "_no_shadow")
    card = "\n".join(retail_card_lines(row, DEFAULT_SETTINGS))
    assert action_from_snapshot(snap) in card
    assert snap.next_fsm_state in card
    assert f"{snap.target_position * 100:.0f}%" in card


def test_invariant_9_10_ledger_roundtrip_and_replay_determinism():
    """Ledger 回环 + 重放确定性：Shadow/Backtest 与 Ledger 使用同一引擎"""
    row = _row("ALLOW", stock="T_INV9")
    snap1 = build_decision_snapshot("FLAT", 0.0, row, DEFAULT_SETTINGS)
    conn = connect()
    try:
        record_snapshot(conn, snap1, "test_invariant_run",
                        pit_grade="C", evidence_grade="D")
        s2 = load_ledger_snapshot(
            conn, "T_INV9", row["decision_date"],
            settings_hash=snap1.settings_hash, run_id="test_invariant_run")
        assert s2 is not None
        # 9) Backtest/Ledger 同源：final_target 一致
        assert abs(float(s2["target_position"]) - snap1.target_position) < 1e-9
        # 10) Shadow 重放确定性：同输入重放结果完全一致
        snap2 = build_decision_snapshot("FLAT", 0.0, row, DEFAULT_SETTINGS)
        assert snap2.next_fsm_state == snap1.next_fsm_state
        assert snap2.target_position == snap1.target_position
        assert snap2.input_fingerprint == snap1.input_fingerprint
    finally:
        conn.execute(
            "DELETE FROM qcfp_decision_ledger WHERE decision_id LIKE 'T_INV9%'")
        conn.commit()
        conn.close()


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_decision_invariants 全部通过 ✅")
