# coding: utf-8
"""Historical Decision Integrity 接 Release 测试（新 89 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.historical_integrity import \
    release_historical_replay_check


def test_hash_change_release_failure():
    r = release_historical_replay_check("H1", "H2", migration_event=None)
    assert r["verdict"] == "RELEASE_FAILURE"
    assert r["allowed"] is False


def test_hash_change_with_migration_event():
    r = release_historical_replay_check(
        "H1", "H2", migration_event={"kind": "CORRECTION",
                                     "reason": "数据修正"})
    assert r["verdict"] == "MIGRATION_RECORDED"
    assert r["allowed"] is True


def test_hash_preserved():
    r = release_historical_replay_check("H1", "H1")
    assert r["verdict"] == "HISTORY_PRESERVED"
    assert r["allowed"] is True
