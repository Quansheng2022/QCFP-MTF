# coding: utf-8
"""Recovery Replay 状态一致性测试（新 77 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.safety.recovery_replay_test import \
    recovery_replay_certificate_required, recovery_state_consistency


def _consistent():
    return {"expected": "X", "actual": "X"}


def test_state_consistent_reactivation():
    r = recovery_state_consistency(_consistent(), _consistent(),
                                   _consistent(), _consistent(),
                                   _consistent(), _consistent(),
                                   _consistent())
    assert r["verdict"] == "REACTIVATION"
    assert r["consistent"] is True


def test_state_mismatch_stays_halted():
    r = recovery_state_consistency(
        {"expected": "H1", "actual": "H2"}, _consistent(),
        _consistent(), _consistent(), _consistent(), _consistent(),
        _consistent())
    assert r["verdict"] == "STAY_DECISION_HALTED"
    assert r["mismatches"] == ["ledger_hash"]


def test_certificate_required():
    r = recovery_replay_certificate_required(service_started=True,
                                             replay_consistent=False)
    assert r["state"] == "DECISION_HALTED"
    assert r["certificate_required"] is True
    r2 = recovery_replay_certificate_required(True, True)
    assert r2["state"] == "RECOVERY_VALIDATION"
