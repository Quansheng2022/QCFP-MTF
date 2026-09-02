# coding: utf-8
"""Human Override Contract 测试（61 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.human_override import explain_divergence, \
    human_override_event


def _event(executed=0.0, otype="OVERRIDE_SKIP"):
    return human_override_event(
        decision_id="d1", canonical_target=0.20,
        override_type=otype, executed_position=executed,
        operator="trader-a", reason_code="MANUAL_RISK",
        timestamp="2026-08-27T09:30:00")


def test_reduce_override_explainable():
    e = _event(executed=0.05, otype="OVERRIDE_REDUCE")
    assert e["executed_position"] == 0.05
    assert e["explainable"] is True
    assert e["escalation_unauthorized"] is False


def test_unauthorized_escalation_detected():
    e = _event(executed=0.40, otype="OVERRIDE_REDUCE")
    assert e["escalation_unauthorized"] is True
    e2 = _event(executed=0.40, otype="OVERRIDE_EXIT")
    # 即使 EXIT，也不能无授权放大到 40%
    assert e2["escalation_unauthorized"] is True


def test_authorized_escalation_allowed():
    e = human_override_event(
        decision_id="d1", canonical_target=0.20,
        override_type="OVERRIDE_REDUCE", executed_position=0.40,
        operator="trader-a", reason_code="AUTHORIZED_RISK_UP",
        timestamp="2026-08-27T09:30:00",
        authorized_escalation=True)
    assert e["escalation_unauthorized"] is False


def test_invalid_override_type():
    try:
        human_override_event("d1", 0.2, "OVERRIDE_MAGIC", 0.0,
                             "op", "RC", "2026-08-27")
        raise AssertionError("should raise")
    except ValueError:
        pass


def test_divergence_explained_by_events():
    r = explain_divergence(0.20, 0.05, [_event(executed=0.05)])
    assert r["diverged"] is True
    assert r["explained"] is True


def test_divergence_without_event_unexplained():
    r = explain_divergence(0.20, 0.05, [])
    assert r["diverged"] is True
    assert r["explained"] is False


def test_no_divergence_no_event_needed():
    r = explain_divergence(0.20, 0.20, [])
    assert r["diverged"] is False
    assert r["explained"] is True
