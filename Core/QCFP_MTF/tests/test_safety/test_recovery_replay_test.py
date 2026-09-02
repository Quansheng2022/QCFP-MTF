# coding: utf-8
"""Recovery Replay Test 测试（77 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.safety.recovery_replay_test import recovery_replay_test


def _decisions():
    return [{"decision_id": f"d{i}", "target": 0.2} for i in range(3)]


def test_recovery_ok_when_consistent():
    r = recovery_replay_test("CKPT-1", _decisions(), _decisions())
    assert r["verified"] is True
    assert r["verdict"] == "RECOVERY_OK"
    assert r["can_return_normal"] is True


def test_recovery_failed_on_mismatch():
    replayed = _decisions()
    replayed[1] = {"decision_id": "d1", "target": 0.6}
    r = recovery_replay_test("CKPT-1", replayed, _decisions())
    assert r["verified"] is False
    assert r["verdict"] == "RECOVERY_FAILED"
    assert r["can_return_normal"] is False
    assert len(r["mismatches"]) == 1


def test_recovery_failed_on_length():
    r = recovery_replay_test("CKPT-1", _decisions(), _decisions()[:2])
    assert r["verdict"] == "RECOVERY_FAILED"
