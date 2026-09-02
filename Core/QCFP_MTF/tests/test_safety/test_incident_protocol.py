# coding: utf-8
"""Production Incident Protocol 测试（39 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.safety.incident_protocol import (INCIDENT_STATES,
                                               incident_protocol,
                                               recover_production)


def test_normal():
    r = incident_protocol()
    assert r["state"] == "NORMAL"
    assert r["halt_new_decisions"] is False


def test_system_failure_halts_new_not_exit():
    r = incident_protocol(failure_kind="SYSTEM_FAILURE")
    assert r["state"] == "DECISION_HALTED"
    assert r["halt_new_decisions"] is True
    assert r["force_exit"] is False     # 系统不可信 ≠ 自动清仓


def test_market_risk_hard_exit():
    r = incident_protocol(failure_kind="MARKET_RISK_HARD_EXIT")
    assert r["state"] == "SAFE_MODE"
    assert r["force_exit"] is True


def test_recovery_requires_replay():
    halted = incident_protocol(failure_kind="SYSTEM_FAILURE")
    r = recover_production(halted, replay_verified=False)
    assert r["recovered"] is False
    assert r["state"] == "RECOVERY_VALIDATION"
    r2 = recover_production(halted, replay_verified=True)
    assert r2["recovered"] is True
    assert r2["state"] == "NORMAL"


def test_states_constant():
    assert INCIDENT_STATES == ("NORMAL", "DEGRADED", "SAFE_MODE",
                               "DECISION_HALTED", "RECOVERY_VALIDATION")
