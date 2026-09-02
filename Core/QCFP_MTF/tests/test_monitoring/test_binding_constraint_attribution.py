# coding: utf-8
"""Binding Constraint Attribution 测试（新 25 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.decision_snapshot import DecisionSnapshot
from QCFP_MTF.monitoring.binding_constraint_frequency import \
    binding_constraint_attribution


def _snap(binding, raw=0.5, final=0.2, trace=None):
    return DecisionSnapshot(
        decision_id=f"{binding}_1", stock_code="S",
        decision_date="2026-08-21",
        institutional_state="ACCUMULATION",
        institutional_permission="ALLOW", permission_cap="TRADE",
        exit_event_kind="NONE", exit_event_reason="", setup_type="BREAKOUT",
        prev_fsm_state="FLAT", next_fsm_state="TESTING",
        previous_position=0.0, target_position=final,
        raw_target_position=raw, binding_constraint=binding,
        constraint_trace={"steps": trace or
                          [{"constraint": binding, "output_value": final},
                           {"constraint": "raw_target",
                            "output_value": raw}]})


def test_attribution_frequencies():
    snaps = [
        _snap("permission_cap"),
        _snap("liquidity_cap"),
        _snap("permission_cap", raw=0.2, final=0.2),
    ]
    r = binding_constraint_attribution(snaps)
    assert r["n_snapshots"] == 3
    assert r["binding_frequency"]["permission_cap"] == \
        round(2 / 3, 4)
    assert r["independent_impact_frequency"]["permission_cap"] == \
        round(1 / 3, 4)
    assert "liquidity_cap" in r["triggered_frequency"]
