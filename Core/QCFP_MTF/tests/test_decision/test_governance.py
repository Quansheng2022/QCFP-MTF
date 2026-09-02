# coding: utf-8
"""2.3 Governance 测试：唯一引擎入口 / Ledger 不可变 / 正式模式门禁"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.common.db import connect
from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.decision.decision_ledger import (audit_identity,
                                               invalidate_snapshot,
                                               load_ledger_snapshot,
                                               record_snapshot)
from QCFP_MTF.decision.decision_snapshot import (LedgerRequiredError,
                                                 build_decision_snapshot,
                                                 build_report_snapshot)
from QCFP_MTF.decision.engine import DecisionConfig, evaluate


def _row(stock="T_GOV", daily="DAILY_BREAKOUT", **kw):
    base = {
        "stock_code": stock,
        "decision_date": "2026-08-21",
        "c_state": "C↑", "f_state": "F↑", "p_state": "P↑",
        "prev_f_state": "F↑",
        "monthly_behavior_state": "Improving",
        "tactical_signal": "Breakout",
        "daily_state": daily,
        "risk_level": "Medium",
        "des_score": 1,
        "chip_stability_confidence": "High",
        "data_quality": "B",
        "q_position_52w": 0.3,
    }
    base.update(kw)
    return base


def test_engine_is_single_entry_point():
    """engine.evaluate == build_decision_snapshot（默认配置同一结果）"""
    row = _row()
    s1 = build_decision_snapshot("FLAT", 0.0, row, DEFAULT_SETTINGS)
    s2 = evaluate(dict(row), "FLAT", 0.0, DEFAULT_SETTINGS)
    assert s1.as_dict() == s2.as_dict()
    assert s1.next_fsm_state in ("TESTING", "BUILDING")   # ALLOW + Breakout
    assert s1.target_position > 0


def test_engine_config_toggles():
    """DecisionConfig 模块开关：A9（Full−Daily）改变 Daily 依赖的结果"""
    row = _row(daily="DAILY_NEUTRAL")
    full = evaluate(dict(row), "FLAT", 0.0, DEFAULT_SETTINGS,
                    config=DecisionConfig())
    no_daily = evaluate(dict(row), "FLAT", 0.0, DEFAULT_SETTINGS,
                        config=DecisionConfig(use_daily=False))
    assert full.next_fsm_state == no_daily.next_fsm_state
    assert full.setup_type == no_daily.setup_type
    assert full.target_position == no_daily.target_position
    row2 = _row(daily="DAILY_BREAKOUT")
    full2 = evaluate(dict(row2), "FLAT", 0.0, DEFAULT_SETTINGS,
                     config=DecisionConfig())
    no_daily2 = evaluate(dict(row2), "FLAT", 0.0, DEFAULT_SETTINGS,
                         config=DecisionConfig(use_daily=False))
    assert full2.setup_type != no_daily2.setup_type  # BREAKOUT vs 中性
    # 无权限（A2）：permission 强制 STRONG_ALLOW
    a2 = evaluate(dict(row2), "FLAT", 0.0, DEFAULT_SETTINGS,
                  config=DecisionConfig(use_permission=False,
                                        use_soft_exit=False,
                                        use_hard_exit=False))
    assert a2.institutional_permission == "STRONG_ALLOW"


def test_ledger_immutable_append_only():
    """Ledger 不可变：同身份只追加一次；不同 run 各自保留；invalidate 不删除"""
    row = _row(stock="T_GOV1")
    snap = evaluate(dict(row), "FLAT", 0.0, DEFAULT_SETTINGS, run_id="run_A")
    identity = audit_identity(snap, "run_A")
    conn = connect()
    try:
        conn.execute("DELETE FROM qcfp_decision_ledger "
                     "WHERE decision_id='T_GOV1_2026-08-21'")
        conn.commit()
        assert record_snapshot(conn, snap, "run_A") == 1
        assert record_snapshot(conn, snap, "run_A") == 0   # 同身份跳过
        n = conn.execute(
            "SELECT COUNT(*) FROM qcfp_decision_ledger "
            "WHERE decision_id='T_GOV1_2026-08-21'").fetchone()[0]
        assert n == 1
        # 不同 run_id → 新身份，追加
        assert record_snapshot(conn, snap, "run_B") == 1
        assert len(identity) == 9   # 2.7：九元审计身份（含 Data Snapshot/Version）
        # invalidate（P0-B 新 4 号）：Append-only 事件，原行不可变
        assert invalidate_snapshot(conn, "T_GOV1_2026-08-21", "run_A",
                                   "run_B") == 1
        rows = conn.execute(
            "SELECT status, run_id FROM qcfp_decision_ledger "
            "WHERE decision_id='T_GOV1_2026-08-21' ORDER BY id"
        ).fetchall()
        assert len(rows) == 3                     # run_A + run_B + 事件
        assert rows[0]["status"] == "ACTIVE"      # 历史事实永不修改
        assert rows[-1]["status"] == "DECISION_INVALIDATED"
        assert rows[-1]["run_id"] == "run_A_EVENT"
        # 原 ACTIVE 行不可变（事实源）；superseded 信息只存在于追加事件
        still = conn.execute(
            "SELECT status, context FROM qcfp_decision_ledger "
            "WHERE decision_id='T_GOV1_2026-08-21' AND run_id='run_A'"
        ).fetchone()
        assert still["status"] == "ACTIVE"
        event = conn.execute(
            "SELECT context FROM qcfp_decision_ledger "
            "WHERE decision_id='T_GOV1_2026-08-21' "
            "AND status='DECISION_INVALIDATED'").fetchone()
        assert json.loads(event["context"])["payload"]["superseded_by"] \
            == "run_B"
    finally:
        conn.execute("DELETE FROM qcfp_decision_ledger "
                     "WHERE decision_id LIKE 'T_GOV1%'")
        conn.commit()
        conn.close()


def test_formal_mode_blocks_fallback():
    """正式模式禁止 FLAT/0 单点重算（必须存在 Ledger）"""
    row = _row(stock="T_GOV2")
    try:
        build_report_snapshot(row, {"backtest": {"mode": "production"}},
                              shadow_dir=Path(__file__).parent / "_no_shadow")
        raise AssertionError("should raise LedgerRequiredError")
    except LedgerRequiredError:
        pass
    # research_exploration 允许 fallback（标注非正式）
    snap, source = build_report_snapshot(
        row, {"backtest": {"mode": "research_exploration"}},
        shadow_dir=Path(__file__).parent / "_no_shadow")
    assert snap is not None
    assert "NON_CANONICAL" in source


def test_participation_budget_observation():
    """2.4 观察仓（Exploratory Exposure）：WATCH + Setup + 低风险 → OBSERVE"""
    row = _row(stock="T_BUD", daily="DAILY_BREAKOUT",
               tactical_signal="Breakout", risk_level="Low",
               c_state="C→", f_state="F→", p_state="P→",
               prev_f_state="F→")
    snap = evaluate(dict(row), "FLAT", 0.0, DEFAULT_SETTINGS)
    assert snap.institutional_permission == "WATCH"      # 权限不变（不可越权）
    assert snap.participation_mode == "OBSERVE"
    assert snap.next_fsm_state == "TESTING"              # 观察例外进入
    assert snap.target_position <= 0.05 + 1e-9           # 观察上限
    assert snap.position_class == "OBSERVATION"
    assert "participation_observe" in snap.override_rule_ids
    # 无 Setup → STAND，不参与
    row2 = dict(row)
    row2.update({"daily_state": "DAILY_NEUTRAL",
                 "tactical_signal": "Consolidation"})
    snap2 = evaluate(row2, "FLAT", 0.0, DEFAULT_SETTINGS)
    assert snap2.participation_mode == "STAND"
    assert snap2.next_fsm_state == "FLAT"
    # BLOCK 永不观察
    row3 = _row(stock="T_BUD", daily="DAILY_BREAKOUT",
                tactical_signal="Breakout", risk_level="Low",
                c_state="C↓", f_state="F↓", p_state="P↓",
                prev_f_state="F↓")
    snap3 = evaluate(row3, "FLAT", 0.0, DEFAULT_SETTINGS)
    assert snap3.institutional_permission == "BLOCK"
    assert snap3.participation_mode == "STAND"
    assert snap3.next_fsm_state == "FLAT"


def test_exit_severity_three_tiers():
    from QCFP_MTF.decision.hard_exit import ExitEvent
    assert ExitEvent("HARD_EXIT").severity == 3          # L3 致命
    assert ExitEvent("STOP_EXIT").severity == 2          # L2 风险性
    assert ExitEvent("FORCED_DELEVERAGE").severity == 2
    assert ExitEvent("RISK_EXIT").severity == 1          # L1 纪律性
    assert ExitEvent("BREAKDOWN").severity == 1
    assert ExitEvent("NONE").severity == 0


def test_trade_quality_gates_target():
    """2.5：允许交易 ≠ 值得交易——TQS 低于门槛时 target 压为 0"""
    row = _row(stock="T_TQ", daily="DAILY_PULLBACK",
               tactical_signal="Pullback", risk_level="Low",
               c_state="C→", f_state="F→", p_state="P→",
               prev_f_state="F→")
    snap = evaluate(dict(row), "FLAT", 0.0, DEFAULT_SETTINGS)
    assert snap.institutional_permission == "WATCH"
    assert snap.participation_mode == "OBSERVE"
    assert snap.target_position > 0                     # 默认门槛 40 通过
    strict = {"decision": {"retail": {"trade_quality": {"min_tradable": 60}}}}
    snap2 = evaluate(dict(row), "FLAT", 0.0, strict)
    assert snap2.target_position == 0.0                 # 门槛 60 → 压仓
    assert snap2.primary_reason == "TRADE_QUALITY_LOW"


def test_governance_ablation_toggles():
    """Full−Stop / Full−Observation 独立开关"""
    # STOP 开关：use_stop=False → STOP_EXIT 不触发
    row = _row(stock="T_STP", daily="DAILY_BREAKOUT",
               tactical_signal="Breakout", risk_level="Low",
               stop_triggered=True)
    full = evaluate(dict(row), "HOLDING", 0.3, DEFAULT_SETTINGS)
    no_stop = evaluate(dict(row), "HOLDING", 0.3, DEFAULT_SETTINGS,
                       config=DecisionConfig(use_stop=False))
    assert full.exit_event_kind == "STOP_EXIT"
    assert no_stop.exit_event_kind == "NONE"
    assert no_stop.next_fsm_state != "EXITING"
    # Observation 开关：use_observation=False → WATCH 不再 OBSERVE
    row2 = _row(stock="T_OBS", daily="DAILY_BREAKOUT",
                tactical_signal="Breakout", risk_level="Low",
                c_state="C→", f_state="F→", p_state="P→",
                prev_f_state="F→")
    obs = evaluate(dict(row2), "FLAT", 0.0, DEFAULT_SETTINGS)
    no_obs = evaluate(dict(row2), "FLAT", 0.0, DEFAULT_SETTINGS,
                      config=DecisionConfig(use_observation=False))
    assert obs.participation_mode == "OBSERVE"
    assert no_obs.participation_mode == "STAND"
    assert no_obs.next_fsm_state == "FLAT"


def test_permission_opportunity_matrix():
    """Permission × Opportunity 二维矩阵（不影响 Permission）"""
    from QCFP_MTF.decision.retail import (PERMISSION_OPPORTUNITY_MATRIX,
                                          opportunity_level,
                                          opportunity_matrix_md)
    assert opportunity_level("BREAKOUT", 72) == "High"
    assert opportunity_level("BREAKOUT", 45) == "Mid"
    assert opportunity_level("NONE", 80) == "Low"
    md = opportunity_matrix_md("WATCH", "High")
    assert "**OBS**" in md
    assert "TRADE" in md
    assert "A+" in PERMISSION_OPPORTUNITY_MATRIX["STRONG_ALLOW"]["High"]


def test_decision_path_and_evidence_grades():
    """P0：Decision Path 含 Budget/TQS/Governance；PIT/证据分级非硬编码"""
    row = _row(stock="T_PTH", daily="DAILY_BREAKOUT",
               tactical_signal="Breakout", risk_level="Low")
    snap = evaluate(dict(row), "FLAT", 0.0, DEFAULT_SETTINGS)
    for step in ("participation_budget", "trade_quality", "governance",
                 "final_target"):
        assert step in snap.decision_path
    assert snap.pit_grade in ("A", "B", "C", "D")
    assert snap.evidence_grade in ("A", "B", "C", "D")
    assert snap.context.get("trace", {}).get("participation") is not None


def test_model_registry_roundtrip():
    """P1：Model Registry settings_hash → settings_blob 可复现且幂等"""
    from QCFP_MTF.decision.decision_ledger import register_model
    conn = connect()
    try:
        assert register_model(conn, DEFAULT_SETTINGS, "M_TEST", "R_TEST",
                              "S_TEST", "F_TEST") == 1
        assert register_model(conn, DEFAULT_SETTINGS, "M_TEST", "R_TEST",
                              "S_TEST", "F_TEST") == 0   # 幂等
        r = conn.execute(
            "SELECT settings_blob, code_commit, python_version FROM "
            "qcfp_model_registry WHERE model_version='M_TEST' "
            "AND rule_version='R_TEST' AND schema_version='S_TEST'"
        ).fetchone()
        assert r is not None
        assert "QCFP-MTF-2.5.0" in r["settings_blob"]
        assert r["python_version"].startswith("3.")
    finally:
        conn.execute("DELETE FROM qcfp_model_registry "
                     "WHERE model_version='M_TEST'")
        conn.commit()
        conn.close()


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_governance 全部通过 ✅")
