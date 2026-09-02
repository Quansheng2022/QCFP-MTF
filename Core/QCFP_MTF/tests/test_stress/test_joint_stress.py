# coding: utf-8
"""Joint Degradation Stress 测试（94 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.stress.joint_stress import JOINT_SCENARIOS, joint_scenario_engine, \
    joint_stress


def test_no_failure_low():
    r = joint_stress(0.1, 0.03)
    assert r.joint_severity == "LOW"
    assert r.exit_feasible is True


def test_joint_failure_critical():
    r = joint_stress(0.3, 0.05, data_degraded=True, model_degraded=True,
                     execution_degraded=True, slippage_multiplier=3.0,
                     liquidity_collapse_pct=0.5)
    assert r.joint_severity == "CRITICAL"
    assert r.worst_case_loss > 0.05
    assert r.exit_feasible is False
    assert len(r.reasons) == 3


def test_partial_failure_high():
    r = joint_stress(0.2, 0.04, data_degraded=True, model_degraded=True)
    assert r.joint_severity == "HIGH"


def test_joint_scenario_engine_18():
    r = joint_scenario_engine(0.3, 0.05, capital=1_000_000)
    assert len(r["scenarios"]) == len(JOINT_SCENARIOS)
    for s in r["scenarios"].values():
        assert "system_state" in s
        assert "capital_remaining" in s
        assert "expected_loss" in s
    assert r["worst_system_state"] in ("DEFENSIVE", "SAFE_MODE", "HALTED")
