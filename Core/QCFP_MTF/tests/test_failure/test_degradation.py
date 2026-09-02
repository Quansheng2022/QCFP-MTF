# coding: utf-8
"""Failure Safe Degradation 测试（39 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.failure.degradation import apply_degradation, \
    failure_degradation


def test_normal_no_failure():
    d = failure_degradation({})
    assert d["status"] == "正常"
    assert d["block_new_risk"] is False


def test_data_failure_tightens_permission():
    d = failure_degradation({"data_failure": True})
    assert d["status"] == "DEGRADED"
    assert d["actions"][0]["action"] == "PERMISSION_TIGHTEN"
    r = apply_degradation(0.2, 0.0, {"data_failure": True})
    assert r["target"] == 0.0


def test_pit_failure_blocks():
    d = failure_degradation({"pit_failure": True})
    assert d["status"] == "BLOCK"
    r = apply_degradation(0.3, 0.1, {"pit_failure": True})
    assert r["target"] == 0.0


def test_replay_failure_halts():
    d = failure_degradation({"replay_failure": True})
    assert d["status"] == "HALTED"


def test_ledger_failure_no_trade():
    d = failure_degradation({"ledger_failure": True})
    assert d["status"] == "BLOCK"
    assert d["actions"][0]["action"] == "NO_TRADE"
