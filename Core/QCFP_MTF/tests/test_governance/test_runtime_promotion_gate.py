# coding: utf-8
"""Runtime Promotion Gate 测试（P0-4：20 日连续 Qualification）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.runtime_promotion_gate import (
    day_qualified, evaluate_decision_support_qualification,
    evaluate_shadow_qualification)


def _day(verdict="EVIDENCE_READY", coverage=1.0, perm=0, pit=0,
         uncertified=0, critical=0, eligible=16, exact=16,
         status="", date="2026-08-21", duplicate=0, identity_break=0,
         outcome_coverage=1.0, matured_5d=16):
    return {"trade_date": date, "verdict": verdict, "status": status,
            "coverage": coverage, "permission_violations": perm,
            "pit_violations": pit,
            "uncertified_executions": uncertified,
            "critical_replay_mismatch": critical,
            "replay_eligible": eligible, "replay_exact": exact,
            "outcome_coverage": outcome_coverage,
            "outcome_maturity_5d": matured_5d,
            "decision_duplicate_count": duplicate,
            "canonical_identity_break": identity_break,
            "evidence_hash": f"H-{date}"}


def test_day_qualified_requires_full_evidence():
    assert day_qualified(_day())[0] is True
    assert day_qualified(_day(coverage=0.9))[0] is False
    assert day_qualified(_day(perm=1))[0] is False
    assert day_qualified(_day(pit=2))[0] is False
    assert day_qualified(_day(uncertified=1))[0] is False
    assert day_qualified(_day(critical=1))[0] is False
    assert day_qualified(_day(eligible=0, exact=0))[0] is False
    assert day_qualified(_day(eligible=16, exact=15))[0] is False
    assert day_qualified(_day(verdict="NOT_PROVEN"))[0] is False


def test_accumulating_then_qualified():
    window = [_day(date=f"2026-08-{i:02d}") for i in range(1, 21)]
    r = evaluate_shadow_qualification(window, required_days=20)
    assert r["state"] == "SHADOW_QUALIFIED"
    assert r["qualified_days"] == 20
    assert r["remaining_days"] == 0
    r2 = evaluate_shadow_qualification(window[:5], required_days=20)
    assert r2["state"] == "SHADOW_ACCUMULATING"
    assert r2["qualified_days"] == 5
    assert r2["remaining_days"] == 15


def test_hard_reset_suspends_and_zeroes():
    window = [_day(date=f"2026-08-{i:02d}") for i in range(1, 8)]
    window[4] = _day(date="2026-08-05", pit=1)
    r = evaluate_shadow_qualification(window, required_days=20)
    assert r["state"] == "SUSPENDED"
    assert r["qualified_days"] == 2   # 重置后 08-06/08-07 重新累计
    assert r["hard_reset_count"] == 1
    assert any("pit_violations" in b for b in r["blocking_reasons"])


def test_not_applicable_does_not_break_streak():
    window = [
        _day(date="2026-08-01"),
        _day(date="2026-08-04", status="NOT_APPLICABLE",
             verdict="NOT_APPLICABLE"),
        _day(date="2026-08-05"),
    ]
    r = evaluate_shadow_qualification(window, required_days=20)
    assert r["state"] == "SHADOW_ACCUMULATING"
    assert r["qualified_days"] == 2


def test_not_proven_breaks_streak():
    window = [
        _day(date="2026-08-01"),
        _day(date="2026-08-04", verdict="NOT_PROVEN"),
        _day(date="2026-08-05"),
    ]
    r = evaluate_shadow_qualification(window, required_days=20)
    assert r["qualified_days"] == 1


def test_decision_support_lifecycle():
    """SHADOW_QUALIFIED → OUTCOME_ACCUMULATING → DECISION_SUPPORT_QUALIFIED"""
    window = [_day(date=f"2026-08-{i:02d}") for i in range(1, 21)]
    r = evaluate_decision_support_qualification(window, shadow_days=20,
                                                outcome_days=20)
    assert r["state"] == "DECISION_SUPPORT_QUALIFIED"
    assert r["shadow_state"] == "SHADOW_QUALIFIED"
    assert r["outcome_days"] == 20
    # Outcome 覆盖不足 → OUTCOME_ACCUMULATING
    weak = [_day(date=f"2026-08-{i:02d}", outcome_coverage=0.3,
                 matured_5d=5) for i in range(1, 21)]
    r2 = evaluate_decision_support_qualification(weak, shadow_days=20,
                                                 outcome_days=20)
    assert r2["state"] == "OUTCOME_ACCUMULATING"
    assert r2["outcome_days"] == 0
    assert r2["remaining_outcome_days"] == 20


def test_decision_support_suspended_on_hard_reset():
    window = [_day(date=f"2026-08-{i:02d}") for i in range(1, 8)]
    window[3] = _day(date="2026-08-04", pit=1)
    r = evaluate_decision_support_qualification(window, shadow_days=20,
                                                outcome_days=20)
    assert r["state"] == "SUSPENDED"


def test_decision_support_60d_observation_non_blocking():
    window = [_day(date=f"2026-08-{i:02d}") for i in range(1, 21)]
    r = evaluate_decision_support_qualification(window, shadow_days=20,
                                                outcome_days=20)
    assert r["observation_60d"]["blocking"] is False
    assert r["observation_60d"]["window_days"] == 20
