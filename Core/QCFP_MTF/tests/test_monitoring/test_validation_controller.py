# coding: utf-8
"""Continuous Validation Controller 测试（70 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.monitoring.validation_controller import (CONTROLLER_STATES,
                                                       controller_to_md,
                                                       validation_controller)


def test_healthy():
    r = validation_controller({"system": "HEALTHY", "model": "HEALTHY",
                               "data": "HEALTHY"})
    assert r.state == "HEALTHY"
    assert r.recovery_required is False


def test_warning_to_halted_ladder():
    r = validation_controller({"system": "WARNING"})
    assert r.state == "WARNING"
    r2 = validation_controller({"system": "DEGRADED", "risk": "REVIEW"})
    assert r2.state == "REVIEW"


def test_critical_failure_halts():
    r = validation_controller({"ledger": "FAIL", "model": "HEALTHY"})
    assert r.state == "HALTED"
    assert r.recovery_required is True
    assert r.recovery_steps == ("ROOT_CAUSE", "RESEARCH", "VALIDATION",
                                "CERTIFICATION", "SHADOW", "PROMOTION")


def test_states_constant():
    assert CONTROLLER_STATES == ("HEALTHY", "WARNING", "DEGRADED",
                                 "REVIEW", "HALTED")


def test_controller_to_md():
    md = controller_to_md(validation_controller({"ledger": "FAIL"}))
    assert "Continuous Validation Controller" in md
    assert "恢复流程" in md
