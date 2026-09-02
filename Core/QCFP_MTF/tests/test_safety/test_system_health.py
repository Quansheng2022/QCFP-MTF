# coding: utf-8
"""System Health / Incident / Kill-Switch 测试（20 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.safety.system_health import HEALTH_DIMENSIONS, system_health


def test_green():
    r = system_health({})
    assert r.status == "GREEN"
    assert r.kill_switch is False


def test_yellow_orange():
    assert system_health({"data": 70}).status == "ORANGE"
    assert system_health({"data": 85, "feature": 80}).status == "YELLOW"


def test_red_and_halt():
    assert system_health({"ledger": 30}).status == "RED"
    r = system_health({"ledger": 0})
    assert r.status == "HALT"
    assert r.kill_switch is True


def test_model_doubt_merged():
    r = system_health({"data": 90}, mdi_score=90)
    assert r.status == "HALT"
    assert any("MODEL_DOUBT" in i for i in r.incidents)


def test_dimensions_constant():
    assert HEALTH_DIMENSIONS == ("data", "feature", "decision", "risk",
                                 "execution", "ledger", "research")
