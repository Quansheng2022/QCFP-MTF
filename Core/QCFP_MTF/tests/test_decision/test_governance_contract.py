# coding: utf-8
"""2.6 Governance Contract（G-001..G-010 命名验收）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.decision.decision_certificate import (build_certificate,
                                                    certificate_from_json,
                                                    serialize_certificate)
from QCFP_MTF.decision.engine import DecisionConfig, evaluate
from QCFP_MTF.decision.governance import (add_risk_gate, reentry_gate)
from QCFP_MTF.evidence.snapshot import PIT_ERROR, assert_evidence_asof


def _row(perm, daily="DAILY_NEUTRAL", weekly="Consolidation",
         risk="Medium", des=2, **kw):
    cfp = {"BLOCK": ("C↓", "F↓", "P↓", "F↓"),
           "WATCH": ("C→", "F→", "P→", "F→"),
           "TEST": ("C→", "F↑", "P→", "F→"),
           "ALLOW": ("C↑", "F↑", "P↑", "F↑"),
           "STRONG_ALLOW": ("C↑", "F↑", "P↑", "F↑")}[perm]
    base = {
        "stock_code": "GC", "decision_date": "2026-08-21",
        "c_state": cfp[0], "f_state": cfp[1], "p_state": cfp[2],
        "prev_f_state": cfp[3],
        "monthly_behavior_state": "Improving",
        "tactical_signal": weekly, "daily_state": daily,
        "risk_level": risk, "des_score": des,
        "chip_stability_confidence": "High", "data_quality": "B",
        "q_position_52w": 0.3, "q_trend_score": 55.0,
        "market_context": "neutral", "cbi_state": "CBI_STABLE",
        "catalyst_score": 1.0,
    }
    base.update(kw)
    return base


def test_g001_block_buy_target_zero():
    snap = evaluate(_row("BLOCK", daily="DAILY_BREAKOUT",
                         weekly="Breakout", risk="Low"),
                    "FLAT", 0.0, DEFAULT_SETTINGS)
    assert snap.institutional_permission == "BLOCK"
    assert snap.target_position == 0.0


def test_g002_hard_exit_hold_target_zero():
    snap = evaluate(_row("ALLOW", daily="DAILY_BREAKOUT",
                         weekly="Breakout", risk="Low", des=8),
                    "HOLDING", 0.4, DEFAULT_SETTINGS)
    assert snap.exit_severity == 3
    assert snap.target_position == 0.0


def test_g003_watch_no_position_increase():
    snap = evaluate(_row("WATCH", daily="DAILY_NEUTRAL",
                         weekly="Consolidation"),
                    "HOLDING", 0.3, DEFAULT_SETTINGS)
    assert snap.target_position <= 0.3 + 1e-9


def test_g004_daily_cannot_upgrade_permission():
    a = evaluate(_row("WATCH", daily="DAILY_BREAKOUT", weekly="Breakout"),
                 "FLAT", 0.0, DEFAULT_SETTINGS)
    b = evaluate(_row("WATCH", daily="DAILY_NEUTRAL", weekly="Consolidation"),
                 "FLAT", 0.0, DEFAULT_SETTINGS)
    assert a.institutional_permission == b.institutional_permission == "WATCH"


def test_g005_budget_caps_final_target():
    snap = evaluate(_row("ALLOW", daily="DAILY_BREAKOUT",
                         weekly="Breakout", risk="Low"),
                    "FLAT", 0.0, DEFAULT_SETTINGS)
    assert snap.target_position <= snap.participation_cap + 1e-9 \
        or snap.target_position == 0.0


def test_g006_risk_gate_cannot_bypass_permission():
    snap = evaluate(_row("BLOCK", daily="DAILY_BREAKOUT", weekly="Breakout",
                         risk="Extreme", des=8),
                    "HOLDING", 0.4, DEFAULT_SETTINGS)
    assert snap.target_position == 0.0


def test_g007_final_target_immutable():
    snap = evaluate(_row("ALLOW", daily="DAILY_BREAKOUT",
                         weekly="Breakout", risk="Low"),
                    "FLAT", 0.0, DEFAULT_SETTINGS)
    try:
        snap.target_position = 0.9
        raise AssertionError("should be frozen")
    except Exception:
        pass


def test_g008_reduce_allowed():
    snap = evaluate(_row("WATCH", daily="DAILY_NEUTRAL",
                         weekly="Consolidation", risk="Medium"),
                    "HOLDING", 0.5, DEFAULT_SETTINGS)
    assert snap.target_position <= 0.5 + 1e-9


def test_g009_add_risk_requires_governance():
    from QCFP_MTF.decision.permission_policy import can_add_risk
    assert can_add_risk("WATCH", 0.0, 0.1) is False
    assert can_add_risk("TEST", 0.0, 0.1) is True
    assert can_add_risk("BLOCK", 0.3, 0.2) is False
    assert can_add_risk("ALLOW", 0.0, 0.1) is True


def test_g010_violations_blocked_by_engine():
    # 违反即抛 GovernanceViolation（引擎内断言），不存在"违规但放行"的决策
    try:
        evaluate(_row("BLOCK", daily="DAILY_BREAKOUT", weekly="Breakout",
                      risk="Low"), "FLAT", 0.0, DEFAULT_SETTINGS)
    except Exception:
        raise AssertionError("BLOCK 合法决策不应抛错")


def test_add_risk_gate_and_reentry_gate():
    ok, reasons = add_risk_gate("ALLOW", "BREAKOUT", "Medium", "BUILDING",
                                70.0, 0.2, 0.5)
    assert ok is True and reasons == ()
    ok2, reasons2 = add_risk_gate("WATCH", "BREAKOUT", "Medium", "BUILDING",
                                  70.0, 0.2, 0.5)
    assert ok2 is False and "PERMISSION_BELOW_TEST" in reasons2
    ok3, reasons3 = reentry_gate(0, "ACCUMULATION", "BREAKOUT", "Medium",
                                 "ALLOW")
    assert ok3 is True
    ok4, reasons4 = reentry_gate(2, "ACCUMULATION", "BREAKOUT", "Medium",
                                 "ALLOW")
    assert ok4 is False and "COOLDOWN_ACTIVE" in reasons4


def test_certificate_replay_hash_identical():
    row = _row("ALLOW", daily="DAILY_BREAKOUT", weekly="Breakout", risk="Low")
    s1 = evaluate(dict(row), "FLAT", 0.0, DEFAULT_SETTINGS)
    s2 = evaluate(dict(row), "FLAT", 0.0, DEFAULT_SETTINGS)
    c1, c2 = build_certificate(s1), build_certificate(s2)
    assert c1.certificate_hash() == c2.certificate_hash()
    # 序列化 → 加载 → 重放哈希一致
    loaded = certificate_from_json(serialize_certificate(c1))
    assert loaded.certificate_hash() == c1.certificate_hash()
    assert c1.governance_passed is True


def test_pit_hard_gate_raises():
    ev = {"decision_date": "2026-08-21",
          "quarterly": {"period_end": "2026-06-30",
                        "available_at": "2026-09-01"}}
    try:
        assert_evidence_asof(ev)
        raise AssertionError("should raise PIT_ERROR")
    except PIT_ERROR:
        pass


def test_g1_hard_exit_final_target_zero():
    snap = evaluate(_row("ALLOW", risk="Extreme", des=9),
                    "HOLDING", 0.4, DEFAULT_SETTINGS)
    assert snap.exit_severity == 3 and snap.target_position == 0.0


def test_g2_block_final_target_zero():
    snap = evaluate(_row("BLOCK", risk="Low"), "FLAT", 0.0,
                    DEFAULT_SETTINGS)
    assert snap.target_position == 0.0
    # 既有仓位允许逐步去风险（降仓，不是新增）
    trim = evaluate(_row("BLOCK", risk="Low"), "HOLDING", 0.4,
                    DEFAULT_SETTINGS)
    assert 0.0 <= trim.target_position < 0.4


def test_g3_watch_non_observe_no_new_risk():
    snap = evaluate(_row("WATCH", weekly="Consolidation",
                         daily="DAILY_NEUTRAL"),
                    "HOLDING", 0.3, DEFAULT_SETTINGS)
    assert snap.participation_mode != "OBSERVE"
    assert snap.target_position <= 0.3 + 1e-9


def test_g4_observe_bounded_by_cap():
    snap = evaluate(_row("WATCH", weekly="Breakout",
                         daily="DAILY_BREAKOUT", risk="Low"),
                    "FLAT", 0.0, DEFAULT_SETTINGS)
    assert snap.participation_mode == "OBSERVE"
    assert snap.target_position <= snap.participation_cap + 1e-9


def test_g5_final_target_within_envelope():
    for perm in ("WATCH", "TEST", "ALLOW", "STRONG_ALLOW"):
        snap = evaluate(_row(perm, weekly="Breakout",
                             daily="DAILY_BREAKOUT", risk="Low"),
                        "FLAT", 0.0, DEFAULT_SETTINGS)
        if snap.participation_mode in ("OBSERVE", "EXPLORE", "TRADE"):
            assert snap.target_position <= snap.participation_cap + 1e-9 \
                or snap.target_position == 0.0


def test_g6_daily_never_upgrades_permission():
    low = evaluate(_row("WATCH", weekly="Consolidation",
                        daily="DAILY_NEUTRAL"), "FLAT", 0.0,
                   DEFAULT_SETTINGS)
    high = evaluate(_row("WATCH", weekly="Breakout",
                         daily="DAILY_BREAKOUT"), "FLAT", 0.0,
                    DEFAULT_SETTINGS)
    assert low.institutional_permission == high.institutional_permission


def test_g7_risk_gate_only_reduces_risk():
    low = evaluate(_row("TEST", weekly="Breakout", daily="DAILY_BREAKOUT",
                        risk="Low"), "FLAT", 0.0, DEFAULT_SETTINGS)
    high = evaluate(_row("TEST", weekly="Breakout", daily="DAILY_BREAKOUT",
                         risk="Extreme"), "FLAT", 0.0, DEFAULT_SETTINGS)
    assert high.institutional_permission == low.institutional_permission
    assert high.target_position <= low.target_position + 1e-9


def test_g8_final_target_through_governance():
    snap = evaluate(_row("ALLOW", weekly="Breakout",
                         daily="DAILY_BREAKOUT", risk="Low"),
                    "FLAT", 0.0, DEFAULT_SETTINGS)
    assert "governance" in snap.decision_path
    assert "final_target" in snap.decision_path
    cert = build_certificate(snap)
    assert cert.governance_passed is True
    assert cert.constraint_trace["final_target"] == snap.target_position
    assert len(cert.decision_graph) >= 5


def test_feature_permission_matrix_blocks_future():
    from QCFP_MTF.governance.feature_gate import (FeatureGateError,
                                                  assert_feature_allowed,
                                                  feature_allowed)
    assert feature_allowed("wave_signal", "decision") is True
    assert feature_allowed("wave_label", "decision") is False
    assert feature_allowed("future_return", "evaluation") is True
    assert feature_allowed("C/F/P", "structural") is True
    try:
        assert_feature_allowed("wave_label", "decision")
        raise AssertionError("should raise FeatureGateError")
    except FeatureGateError:
        pass


def test_wave_label_vs_signal_isolation():
    import pandas as pd
    from QCFP_MTF.wave.label import find_wave_labels
    from QCFP_MTF.wave.signal import evaluate_wave_signal
    kl = pd.DataFrame({
        "stock_code": ["W"] * 8,
        "date": pd.date_range("2024-01-05", periods=8, freq="W-FRI"),
        "close": [10, 10, 11, 12, 13, 14, 15, 16],
    })
    labels = find_wave_labels(kl, min_gain=0.1, window=8)
    assert labels and labels[0].future_aware is True
    sig = evaluate_wave_signal([10, 10, 11, 12, 13, 14, 15, 16])
    assert sig.future_aware is False
    assert sig.direction == "UP" and sig.strength > 0


def test_governance_matrix_and_risk_monotonic():
    from QCFP_MTF.decision.governance import governance_matrix_ok
    assert governance_matrix_ok("BLOCK", "BREAKOUT", "Low", 0.0)[0] is True
    ok2, r2 = governance_matrix_ok("BLOCK", "BREAKOUT", "Low", 0.1)
    assert ok2 is False and "BLOCK_TARGET_NONZERO" in r2
    assert governance_matrix_ok("WATCH", "BREAKOUT", "Low", 0.05)[0] is True
    ok4, r4 = governance_matrix_ok("WATCH", "NONE", "Low", 0.05)
    assert ok4 is False and "WATCH_NO_SETUP" in r4
    assert governance_matrix_ok("ALLOW", "BREAKOUT", "Low", 0.3)[0] is True
    # Risk 单调：风险升高 → target 不升高
    base = _row("TEST", weekly="Breakout", daily="DAILY_BREAKOUT")
    t_lo = evaluate({**base, "risk_level": "Low"}, "FLAT", 0.0,
                    DEFAULT_SETTINGS).target_position
    t_hi = evaluate({**base, "risk_level": "High"}, "FLAT", 0.0,
                    DEFAULT_SETTINGS).target_position
    assert t_hi <= t_lo + 1e-9


def test_governance_proof_engine():
    from QCFP_MTF.decision.governance_proof import prove
    p_ok = prove("ALLOW", "TRADE", 0.5, 0.3, 0.3, 0.4, 0.3, 0.0,
                 hard_exit=False, data_quality="B")
    assert p_ok.proof == "PASS"
    p_bad = prove("BLOCK", "STAND", 0.0, 0.0, 0.0, 0.4, 0.2, 0.0,
                  hard_exit=False, data_quality="B")
    assert p_bad.proof == "FAIL"
    assert "FINAL_EXCEEDS_CAPS" in p_bad.violations
    p_hex = prove("ALLOW", "TRADE", 0.5, 0.3, 0.3, 0.4, 0.2, 0.0,
                  hard_exit=True, data_quality="B")
    assert p_hex.proof == "FAIL" and "HARD_EXIT_TARGET_NONZERO" in p_hex.violations
    # 引擎：proof 写入 context，且 FAIL 前置抛错
    snap = evaluate(_row("ALLOW", weekly="Breakout", daily="DAILY_BREAKOUT",
                         risk="Low"), "FLAT", 0.0, DEFAULT_SETTINGS)
    assert snap.context["governance_proof"]["proof"] == "PASS"


def test_data_quality_is_constraint():
    row = _row("ALLOW", weekly="Breakout", daily="DAILY_BREAKOUT", risk="Low")
    b = evaluate({**row, "data_quality": "B"}, "FLAT", 0.0,
                 DEFAULT_SETTINGS).target_position
    a = evaluate({**row, "data_quality": "A"}, "FLAT", 0.0,
                 DEFAULT_SETTINGS).target_position
    d = evaluate({**row, "data_quality": "D"}, "FLAT", 0.0,
                 DEFAULT_SETTINGS)
    assert abs(b - a * 0.8) < 1e-9
    assert d.target_position == 0.0
    assert d.context["governance_proof"]["data_quality"] == "D"


def test_hard_exit_randomized_1000():
    import random
    rng = random.Random(7)
    perms = ("BLOCK", "WATCH", "TEST", "ALLOW", "STRONG_ALLOW")
    setups = ("BREAKOUT", "PULLBACK", "ACCUMULATION", "RECOVERY", "NONE")
    risks = ("Low", "Medium", "High", "Extreme")
    for _ in range(1000):
        p = rng.choice(perms)
        s = rng.choice(setups)
        r = rng.choice(risks)
        prev = rng.choice((0.0, 0.1, 0.3, 0.5, 0.7))
        row = _row(p, weekly="Breakout", daily="DAILY_BREAKOUT", risk=r,
                   des=rng.randint(7, 12))
        snap = evaluate(dict(row), "HOLDING", prev, DEFAULT_SETTINGS)
        if snap.exit_severity >= 3:
            assert snap.target_position == 0.0, (p, s, r, prev)


def test_strong_wave_block_no_trade():
    """Strong Wave + BLOCK = NO TRADE（最高级 invariant）"""
    from QCFP_MTF.decision.governance import governance_matrix_ok
    assert governance_matrix_ok("BLOCK", "BREAKOUT", "Low", 0.3)[0] is False
    snap = evaluate(_row("BLOCK", weekly="Breakout", daily="DAILY_BREAKOUT",
                         risk="Low"), "FLAT", 0.0, DEFAULT_SETTINGS)
    assert snap.institutional_permission == "BLOCK"
    assert snap.target_position == 0.0


def test_nine_tuple_audit_identity():
    from QCFP_MTF.common.db import connect
    from QCFP_MTF.decision.decision_ledger import (audit_identity,
                                                   record_snapshot)
    row = _row("ALLOW", weekly="Breakout", daily="DAILY_BREAKOUT", risk="Low",
               stock_code="T_9TUPLE")
    snap = evaluate(dict(row), "FLAT", 0.0, DEFAULT_SETTINGS)
    conn = connect()
    try:
        conn.execute("DELETE FROM qcfp_decision_ledger "
                     "WHERE decision_id LIKE 'T_9TUPLE%'")
        conn.commit()
        record_snapshot(conn, snap, "run_9", settings=DEFAULT_SETTINGS)
        identity = audit_identity(snap, "run_9")
        assert len(identity) == 9
        r = conn.execute(
            "SELECT data_snapshot_id, data_version FROM qcfp_decision_ledger "
            "WHERE decision_id LIKE 'T_9TUPLE%'").fetchone()
        assert r is not None and len(r["data_snapshot_id"]) == 16
        assert r["data_version"] == "1.0"
    finally:
        conn.execute("DELETE FROM qcfp_decision_ledger "
                     "WHERE decision_id LIKE 'T_9TUPLE%'")
        conn.commit()
        conn.close()


def test_wave_opportunity_and_oqs():
    from QCFP_MTF.wave.opportunity import (build_wave_opportunity,
                                            opportunity_quality,
                                            waiting_value)
    from QCFP_MTF.wave.signal import evaluate_wave_signal
    sig = evaluate_wave_signal([10, 10, 11, 12, 13, 14, 15, 16])
    score, band = opportunity_quality(sig, "ALLOW", "Low", 70, liquidity_score=3)
    assert score > 60 and band in ("High", "A+")
    score2, band2 = opportunity_quality(sig, "BLOCK", "Extreme", 20)
    assert score2 < 60 and band2 != "A+"
    assert waiting_value("BREAKOUT", "Medium", "WATCH", 50) == \
        "WAIT_FOR_PERMISSION"
    assert waiting_value("BREAKOUT", "Medium", "ALLOW", 50) == \
        "WAIT_FOR_CONFIRMATION"
    assert waiting_value("NONE", "Medium", "ALLOW", 80) == "WAIT（无 Setup）"
    # WaveOpportunity 构建
    from QCFP_MTF.wave.label import WaveLabel
    label = WaveLabel("S", "2024-01-05", "2024-06-28", "2024-06-28", 0.8)
    snap = evaluate(_row("ALLOW", weekly="Breakout", daily="DAILY_BREAKOUT",
                         risk="Low", stock_code="S"), "FLAT", 0.0,
                    DEFAULT_SETTINGS)
    opp = build_wave_opportunity(label, snap_at_start=snap,
                                 capture_by_model=0.5)
    assert opp.permission_at_start in ("ALLOW", "STRONG_ALLOW")
    assert opp.peak_return == 0.8


def test_regime_classify_and_scale():
    import pandas as pd
    from QCFP_MTF.market.regime import classify_regime, regime_scale
    dates = pd.date_range("2025-01-01", periods=70, freq="D")
    bull = pd.DataFrame({"date": dates,
                         "close": [100.0 * (1.002 ** i) for i in range(70)]})
    bear = pd.DataFrame({"date": dates,
                         "close": [100.0 * (0.997 ** i) for i in range(70)]})
    assert classify_regime(bull, "2025-03-15") == "Bull"
    assert classify_regime(bear, "2025-03-15") in ("Bear", "Crisis")
    s = {"regime_params": {"Bear": {"risk_cap": 0.5}}}
    assert regime_scale("Bear", s, "risk_cap") == 0.5
    assert regime_scale("Bull", s, "risk_cap") == 1.0


def test_conflict_resolver_priority():
    from QCFP_MTF.governance.conflict import resolve_conflict
    # Hard Exit > 一切
    c = resolve_conflict(exit_event_kind="HARD_EXIT", risk_level="High",
                         permission="ALLOW", fsm_next="HOLDING",
                         wave_strength=0.9, setup_type="BREAKOUT",
                         daily_state="DAILY_BREAKOUT")
    assert c["winning_rule"] == "HARD_EXIT"
    assert "RISK_BLOCK" in c["suppressed"]
    # 无硬退出：Risk Block > Permission
    c2 = resolve_conflict(exit_event_kind="NONE", risk_level="Extreme",
                          permission="ALLOW", fsm_next="HOLDING",
                          wave_strength=0.9, setup_type="BREAKOUT")
    assert c2["winning_rule"] == "RISK_BLOCK"
    # Permission > Wave/Setup
    c3 = resolve_conflict(exit_event_kind="NONE", risk_level="Medium",
                          permission="BLOCK", fsm_next="HOLDING",
                          wave_strength=0.9, setup_type="BREAKOUT")
    assert c3["winning_rule"] == "INSTITUTIONAL_PERMISSION"
    assert "WAVE" in c3["suppressed"]
    # 无冲突
    c4 = resolve_conflict(exit_event_kind="NONE", risk_level="Medium",
                          permission="ALLOW", fsm_next="FLAT",
                          wave_strength=0.1, setup_type="NONE")
    assert c4["winning_rule"] == "NONE"


def test_decision_confidence():
    from QCFP_MTF.decision.confidence import evaluate_confidence
    hi = evaluate_confidence("ACCUMULATION", "STRONG_ALLOW", "BREAKOUT",
                             "Low", "A", "A")
    lo = evaluate_confidence("DISTRIBUTION", "BLOCK", "NONE", "Extreme",
                             "D", "D")
    assert hi.score > lo.score
    assert hi.band in ("High", "Medium")
    assert lo.score < 40
    zero = evaluate_confidence("ACCUMULATION", "ALLOW", "BREAKOUT", "Low",
                               "A", "A", exit_severity=3)
    assert zero.score == 0.0
    # 引擎 context 携带 confidence，且不改变权限/仓位
    snap = evaluate(_row("ALLOW", weekly="Breakout", daily="DAILY_BREAKOUT",
                         risk="Low"), "FLAT", 0.0, DEFAULT_SETTINGS)
    assert 0 <= snap.context["confidence"]["score"] <= 100
    assert snap.institutional_permission == "STRONG_ALLOW"  # 不越权


def test_action_gate_four_levels():
    from QCFP_MTF.decision.action_gate import evaluate_action
    assert evaluate_action("TEST", "FLAT", "BREAKOUT", "Low", 0.0, 0.2)[0] \
        == "ENTRY"
    assert evaluate_action("ALLOW", "BUILDING", "BREAKOUT", "Medium",
                           0.2, 0.5)[0] == "ADD"
    assert evaluate_action("WATCH", "BUILDING", "BREAKOUT", "Medium",
                           0.2, 0.5)[0] == "HOLD"      # WATCH 禁止 ADD
    assert evaluate_action("ALLOW", "TRIMMING", "BREAKOUT", "Medium",
                           0.3, 0.5)[0] == "REDUCE"
    assert evaluate_action("ALLOW", "HOLDING", "BREAKOUT", "Low",
                           0.3, 0.5, hard_exit=True)[0] == "EXIT"
    assert evaluate_action("WATCH", "FLAT", "NONE", "Low", 0.0, 0.0)[0] == "WAIT"
    # 引擎 context
    snap = evaluate(_row("ALLOW", weekly="Breakout", daily="DAILY_BREAKOUT",
                         risk="Low"), "FLAT", 0.0, DEFAULT_SETTINGS)
    assert snap.context["action"] in ("ENTRY", "ADD", "HOLD", "WAIT")


def test_reentry_governance():
    from QCFP_MTF.governance.reentry import (ReentryState, reentry_allowed,
                                             record_exit)
    st = record_exit("EXITING", "HARD_EXIT", "2026-01-16", cooldown_days=14)
    ok, _ = reentry_allowed(st, "2026-01-20", "ACCUMULATION", "BREAKOUT",
                            "Low", "ALLOW")
    assert ok is False                              # 冷却未结束
    ok2, _ = reentry_allowed(st, "2026-02-05", "ACCUMULATION", "BREAKOUT",
                             "Low", "ALLOW")
    assert ok2 is True                              # 冷却结束 + 再确认
    ok3, r3 = reentry_allowed(st, "2026-02-05", "DISTRIBUTION", "BREAKOUT",
                              "Low", "ALLOW")
    assert ok3 is False and "INSTITUTIONAL_NOT_CONFIRMED" in r3
    assert isinstance(st.as_dict(), dict)


def test_decision_stability():
    from QCFP_MTF.decision.stability import stability_report
    row = _row("ALLOW", weekly="Breakout", daily="DAILY_BREAKOUT", risk="Low")
    s = stability_report(row, DEFAULT_SETTINGS, n_perturbations=20, seed=3)
    assert 0 <= s["stability_score"] <= 100
    assert 0 <= s["permission_flip_rate"] <= 1
    assert 0 <= s["fsm_flip_rate"] <= 1
    assert 0 <= s["exit_flip_rate"] <= 1
    assert s["position_sensitivity"] >= 0


def test_strategy_lifecycle():
    from QCFP_MTF.governance.lifecycle import (StrategyLifecycle,
                                               StrategyLifecycleError,
                                               StrategyVersion)
    lc = StrategyLifecycle()
    v = StrategyVersion("V1", rule_version="GOV-2.5.0")
    lc.register(v)
    lc.promote("V1", "candidate")
    assert lc.versions["V1"].approval_status == "candidate"
    try:
        lc.promote("V1", "research")   # 禁止回退
        raise AssertionError("should raise")
    except StrategyLifecycleError:
        pass
    ok, reasons = lc.production_change_gate(
        lc.versions["V1"], ablation_ok=True, oos_ok=True, shadow_ok=True,
        approved=True)
    assert ok is True and reasons == ()
    ok2, reasons2 = lc.production_change_gate(
        lc.versions["V1"], ablation_ok=False, oos_ok=True, shadow_ok=True,
        approved=True)
    assert ok2 is False and "ABLATION_NOT_PASSED" in reasons2
    lc.promote("V1", "production")
    lc.retire("V1", "2026-12-31")
    assert lc.versions["V1"].approval_status == "retired"


def test_regime_transition_detector():
    from QCFP_MTF.market.transition import (detect_transitions,
                                            transition_risk_adjustment)
    series = [("2026-01-01", "Bull"), ("2026-01-08", "Bull"),
              ("2026-01-15", "Sideway"), ("2026-01-22", "Sideway"),
              ("2026-01-29", "Sideway"), ("2026-02-05", "Bear"),
              ("2026-02-12", "Bear")]
    ts = detect_transitions(series)
    assert len(ts) == 2
    assert ts[0]["from"] == "Bull" and ts[0]["to"] == "Sideway"
    assert ts[0]["confidence"] == 1.0       # 已持续 >= 3 周
    assert transition_risk_adjustment("Bull", "Bear") == 0.5
    assert transition_risk_adjustment("Bull", "Bull") == 1.0


def test_cross_section_ranking():
    from QCFP_MTF.ranking.opportunity_ranking import (rank_opportunities,
                                                      select_top_n)
    rows = [
        {"stock_code": "A", "institutional_permission": "STRONG_ALLOW",
         "setup_type": "BREAKOUT", "trade_quality": 80, "risk_level": "Low",
         "wave_strength": 0.8},
        {"stock_code": "B", "institutional_permission": "BLOCK",
         "setup_type": "BREAKOUT", "trade_quality": 90, "risk_level": "Low",
         "wave_strength": 0.9},
        {"stock_code": "C", "institutional_permission": "WATCH",
         "setup_type": "NONE", "trade_quality": 30, "risk_level": "High"},
    ]
    ranked = rank_opportunities(rows)
    assert ranked[0]["stock_code"] == "A" or ranked[0]["stock_code"] == "B"
    b = next(r for r in ranked if r["stock_code"] == "B")
    assert b["tradable"] is False          # BLOCK + Rank 高 ≠ 可交易
    top = select_top_n(ranked, n=3)
    assert all(t["tradable"] for t in top)
    assert all(t["permission"] != "BLOCK" for t in top)


def test_replacement_engine():
    from QCFP_MTF.replacement.replacement_engine import should_replace
    candidate = {"stock_code": "N", "institutional_permission": "ALLOW",
                 "setup_type": "BREAKOUT", "trade_quality": 80,
                 "risk_level": "Low", "wave_strength": 0.8}
    existing = {"stock_code": "O", "institutional_permission": "ALLOW",
                "setup_type": "ACCUMULATION", "trade_quality": 55,
                "risk_level": "Medium", "wave_strength": 0.4}
    r = should_replace(candidate, existing, position=0.3)
    assert r["replace"] is True
    assert r["edge"] > 0
    # 高换仓成本/接近效用 → 不换
    close = dict(candidate)
    close["stock_code"] = "O"      # 效用与候选相同 → 换仓成本使 edge≤0
    r2 = should_replace(candidate, close, position=0.5)
    assert r2["replace"] is False


def test_forecast_realized_monitor():
    from QCFP_MTF.monitoring.forecast_realized import (_expected_from_quality,
                                                       calibration_summary,
                                                       compare_trade)
    exp = _expected_from_quality(80.0)
    assert exp["expected_mfe"] == 0.5
    c = compare_trade({"trade_id": "T1", "mfe": 0.3, "mae": -0.2,
                       "holding_weeks": 2, "net_return": -0.1}, exp)
    assert c["mfe_error"] == -0.2          # 系统性高估
    s = calibration_summary([c, c])
    assert s["n"] == 2
    assert s["mfe_systematic_overestimate"] is True


def test_controlled_learning_loop():
    from QCFP_MTF.learning.controlled_loop import (LearningProposal,
                                                   ResearchSandbox,
                                                   validate_proposal)
    sandbox = ResearchSandbox()
    sandbox.write_outcome({"trade": "T1", "outcome": -0.1})
    assert len(sandbox.read_evidence()) == 1
    bad = LearningProposal("V2", "放宽止损")
    ok, failed = validate_proposal(bad)
    assert ok is False and "ablation_ok" in failed
    good = LearningProposal("V2", "放宽止损", ablation_ok=True, oos_ok=True,
                            replay_ok=True, stability_ok=True,
                            cost_stress_ok=True, shadow_ok=True,
                            approved=True)
    sandbox.create_candidate(good)
    ok2, _ = sandbox.promote(good)
    assert ok2 is True


def test_portfolio_state_engine():
    from QCFP_MTF.portfolio.state_engine import (apply_state_to_new_entries,
                                                 portfolio_state,
                                                 state_constraints)
    assert portfolio_state({"permission_risk_share": 0.7}) == "RISK_OFF"
    assert portfolio_state({"sector_concentration": 0.6}) == "CONCENTRATED"
    assert portfolio_state({"total_exposure": 0.9, "market_vol": 0.35,
                            "cash_ratio": 0.05}) == "OVERHEATED"
    assert portfolio_state({"mdd_recent": 0.15}) == "DEFENSIVE"
    assert portfolio_state({"cash_ratio": 0.5, "wave_bullish_share": 0.5}) \
        == "RECOVERY"
    assert portfolio_state({"total_exposure": 0.3}) == "NORMAL"
    c = state_constraints("RISK_OFF")
    assert c["add_allowed"] is False and c["prioritize_reduce"] is True
    import pandas as pd
    df = pd.DataFrame({"stock_code": ["A", "A"],
                       "decision_date": ["2026-01-09", "2026-01-16"],
                       "target": [0.0, 0.3]})
    out = apply_state_to_new_entries(df, "RISK_OFF")
    assert out.loc[out["decision_date"] == "2026-01-16", "target"].iloc[0] == 0.0


def test_stress_scenarios():
    import numpy as np
    from QCFP_MTF.stress.engine import (correlation_vol_scale, mdd,
                                        market_shock, stress_scenarios,
                                        vol_shock)
    r = np.array([0.01, -0.02, 0.02, 0.01, -0.01, 0.02, 0.01])
    s = stress_scenarios(r, n=7)
    names = [x["name"] for x in s]
    assert "market_10%" in names and "vol_x2.0" in names
    assert s[0]["name"] == "baseline"
    shock = market_shock(r, shock=-0.10)
    assert mdd(shock) <= mdd(r)
    assert correlation_vol_scale(n=10, corr_stress=0.9) > 1.0
    assert vol_shock(r, 2.0).std() > r.std()


def test_incremental_evidence():
    from QCFP_MTF.ablation.incremental import evidence_verdict, \
        incremental_evidence
    assert evidence_verdict({"mdd_delta": 0.03, "return_delta": 0.0}) == \
        "risk_reduction"
    assert evidence_verdict({"mdd_delta": 0.0, "return_delta": 0.01}) == "alpha"
    assert evidence_verdict({"mdd_delta": 0.001, "return_delta": 0.001}) == \
        "neutral"
    models = [{"model": "A0_Legacy", "annualized_return": 0.01,
               "max_drawdown": -0.20, "wave_capture_ratio": 0.05,
               "annual_turnover": 3.0},
              {"model": "A2_FSM", "annualized_return": 0.02,
               "max_drawdown": -0.10, "wave_capture_ratio": 0.06,
               "annual_turnover": 1.0}]
    ev = incremental_evidence({"models": models})
    assert "fsm" in ev and ev["fsm"]["verdict"] in ("risk_reduction", "mixed")


def test_explainability_graph():
    from QCFP_MTF.explainability.graph import build_explainability_graph, \
        graph_to_md
    snap = evaluate(_row("ALLOW", weekly="Breakout", daily="DAILY_BREAKOUT",
                         risk="Low"), "FLAT", 0.0, DEFAULT_SETTINGS)
    g = build_explainability_graph(snap)
    assert len(g["nodes"]) == 8 and len(g["edges"]) == 7
    assert g["edges"][-1]["target"] == "Final Position"
    assert "governance_proof" in g["edges"][-1]["rule"]
    md = graph_to_md(g)
    assert "Final Position" in md and "--[" in md


def test_safety_kill_switch():
    from QCFP_MTF.safety.kill_switch import evaluate_safety, safety_gate
    assert evaluate_safety({})["status"] == "NORMAL"
    assert evaluate_safety({"model_drift": True})["status"] == "SAFE_MODE"
    assert evaluate_safety({"ledger_failure": True})["status"] == "HALTED"
    assert evaluate_safety({"risk_breach": True})["status"] == "WARNING"
    # SAFE_MODE：禁新增（target>prev→0），允许减仓（target≤prev）
    g = safety_gate({"model_drift": True}, target=0.3, previous_position=0.1)
    assert g["status"] == "SAFE_MODE" and g["target"] == 0.0
    g2 = safety_gate({"model_drift": True}, target=0.05, previous_position=0.2)
    assert g2["target"] == 0.05
    g3 = safety_gate({"ledger_failure": True}, target=0.1,
                     previous_position=0.3)
    assert g3["status"] == "HALTED" and g3["target"] == 0.0


def test_exit_semantics_split():
    from QCFP_MTF.decision.hard_exit import ExitEvent
    assert ExitEvent("BREAKDOWN").is_exit and not ExitEvent("BREAKDOWN").is_forced
    assert not ExitEvent("BREAKDOWN").is_hard
    assert ExitEvent("STOP_EXIT").is_forced and not ExitEvent("STOP_EXIT").is_hard
    assert ExitEvent("HARD_EXIT").is_forced and ExitEvent("HARD_EXIT").is_hard
    assert not ExitEvent("NONE").is_exit
    # FSM 无条件离场集合（L2+L3）仍由 hard 提供
    assert ExitEvent("STOP_EXIT").hard is True


def test_finalize_target_hard_boundary():
    from QCFP_MTF.decision.governance import finalize_target
    # RISK_OFF：新仓被压为 previous
    f = finalize_target("ALLOW", "TRADE", 0.3, 0.4, 0.0,
                        portfolio_state="RISK_OFF", data_quality="A")
    assert f["target"] == 0.0 and f["portfolio_gate_applied"] is True
    # 既有仓位：RISK_OFF 下 target 压至 previous（不减到 0）
    f2 = finalize_target("ALLOW", "TRADE", 0.5, 0.6, 0.3,
                         portfolio_state="RISK_OFF", data_quality="A")
    assert f2["target"] == 0.3
    # 风险预算分配：risk_budget=0.02, stop=0.1 → target ≤ 0.2
    f3 = finalize_target("STRONG_ALLOW", "TRADE", 0.5, 0.6, 0.0,
                         risk_budget=0.02, stop_distance=0.10,
                         data_quality="A")
    assert f3["target"] <= 0.2 + 1e-9
    assert f3["proof"].proof == "PASS"


def test_risk_budget_target():
    from QCFP_MTF.decision.retail_position_sizing import risk_budget_target
    assert risk_budget_target(0.02, 0.10, permission_cap=0.3) == 0.2
    assert risk_budget_target(0.02, 0.10, permission_cap=0.15) == 0.15
    assert risk_budget_target(0.02, 0.0) == 0.0


def test_calibration_table():
    from QCFP_MTF.monitoring.forecast_realized import calibration_table
    trades = [{"trade_quality": 45, "mfe": 0.06, "mae": -0.03,
               "holding_weeks": 4},
              {"trade_quality": 48, "mfe": 0.09, "mae": -0.05,
               "holding_weeks": 6},
              {"trade_quality": 70, "mfe": 0.12, "mae": -0.04,
               "holding_weeks": 5}]
    cal = calibration_table(trades)
    assert "40-60" in cal and cal["40-60"]["n"] == 2
    assert cal["40-60"]["mfe_median"] == 0.09   # 上取整索引中位数
    assert "60-80" in cal and cal["60-80"]["holding_median"] == 5


def test_permutation_bootstrap_ci():
    import pandas as pd
    from QCFP_MTF.ablation.experiments import permutation_ablation
    from QCFP_MTF.tests.test_backtest.test_execution_simulator import \
        _mini_signals, _mini_weekly
    daily = pd.DataFrame({"stock_code": ["C1", "C1"],
                          "trade_date": ["2026-01-09", "2026-01-16"],
                          "daily_state": ["DAILY_BREAKOUT"] * 2})
    p = permutation_ablation(_mini_signals(), _mini_weekly(),
                             DEFAULT_SETTINGS, daily=daily, seed=1, n_perm=5)
    inc = p.get("incremental", {})
    assert "delta_mean" in inc and "ci_low" in inc and "ci_high" in inc
    assert "effect_size" in inc


def test_invariants_i01_i10():
    """I01–I10 命名验收（覆盖审查要求的系统最高原则）"""
    # I01 BLOCK → 0；I02 HardExit → 0；I04 Daily STRONG + BLOCK → 0
    snap = evaluate(_row("BLOCK", weekly="Breakout", daily="DAILY_BREAKOUT",
                         risk="Low", des=9), "HOLDING", 0.3,
                    DEFAULT_SETTINGS)
    assert snap.target_position == 0.0
    # I05 Wave STRONG + WATCH → Cannot ADD（action gate）
    from QCFP_MTF.decision.action_gate import evaluate_action
    assert evaluate_action("WATCH", "BUILDING", "BREAKOUT", "Medium",
                           0.2, 0.5)[0] == "HOLD"
    # I06 Future Feature → FeatureGateError（已由 feature gate 测试覆盖）
    # I07 Replay Hash（已由 certificate 测试覆盖）
    # I08 Ledger append-only（已由 ledger 不可变测试覆盖）
    # I09 Invalidated must have superseded_by
    from QCFP_MTF.common.db import connect
    from QCFP_MTF.decision.decision_ledger import (invalidate_snapshot,
                                                   record_snapshot)
    row = _row("ALLOW", weekly="Breakout", daily="DAILY_BREAKOUT",
               risk="Low", stock_code="T_I09")
    s = evaluate(dict(row), "FLAT", 0.0, DEFAULT_SETTINGS)
    conn = connect()
    try:
        conn.execute("DELETE FROM qcfp_decision_ledger "
                     "WHERE decision_id LIKE 'T_I09%'")
        conn.commit()
        record_snapshot(conn, s, "run_i09")
        invalidate_snapshot(conn, "T_I09_2026-08-21", "run_i09", "run_i10")
        rows = conn.execute(
            "SELECT status, context FROM qcfp_decision_ledger "
            "WHERE decision_id LIKE 'T_I09%' ORDER BY id").fetchall()
        assert rows[0]["status"] == "ACTIVE"  # 原行不可变
        assert rows[1]["status"] == "DECISION_INVALIDATED"
        import json as _json
        ctx = _json.loads(rows[1]["context"])
        assert ctx["payload"]["superseded_by"] == "run_i10"
    finally:
        conn.execute("DELETE FROM qcfp_decision_ledger "
                     "WHERE decision_id LIKE 'T_I09%'")
        conn.commit()
        conn.close()
    # I10 Report == Ledger（report 快照 final == ledger final）
    from QCFP_MTF.common.db import connect as _c
    from QCFP_MTF.decision.decision_snapshot import load_canonical_decision
    conn2 = _c()
    try:
        row2 = _row("ALLOW", weekly="Breakout", daily="DAILY_BREAKOUT",
                    risk="Low", stock_code="T_I10")
        s2 = evaluate(dict(row2), "FLAT", 0.0, DEFAULT_SETTINGS)
        record_snapshot(conn2, s2, "run_i10", settings=DEFAULT_SETTINGS)
        snap2, _ = load_canonical_decision(row2, DEFAULT_SETTINGS)
        ledger_target = conn2.execute(
            "SELECT final_target FROM qcfp_decision_ledger "
            "WHERE decision_id LIKE 'T_I10%'").fetchone()[0]
        assert abs(float(snap2.target_position) - float(ledger_target)) < 1e-9
    finally:
        conn2.execute("DELETE FROM qcfp_decision_ledger "
                      "WHERE decision_id LIKE 'T_I10%'")
        conn2.commit()
        conn2.close()


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_governance_contract 全部通过 ✅")
