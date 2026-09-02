# coding: utf-8
"""Opportunity Queue / Watchlist 测试（55 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.ranking.queue import OpportunityQueue, evaluate_queue_status


def test_queue_status_transitions():
    # Entry LATE + TEST → TEST（观察）
    assert evaluate_queue_status("TEST", "LATE")[0] == "TEST"
    # Entry OPTIMAL + ALLOW → READY
    assert evaluate_queue_status("ALLOW", "OPTIMAL")[0] == "READY"
    # Entry EARLY + ALLOW → WATCH（等更好位置）
    assert evaluate_queue_status("ALLOW", "EARLY")[0] == "WATCH"
    # BLOCK → BLOCKED
    assert evaluate_queue_status("BLOCK", "OPTIMAL")[0] == "BLOCKED"
    # 过期 → EXPIRED
    assert evaluate_queue_status("ALLOW", "OPTIMAL", age_days=100,
                                 max_age_days=90)[0] == "EXPIRED"


def test_opportunity_queue_auto_update():
    q = OpportunityQueue()
    q.auto_update("A", permission="TEST", entry_timing="LATE",
                  wave_stage="ACTIVE")
    assert q.items["A"].state == "TEST"
    q.auto_update("A", permission="ALLOW", entry_timing="OPTIMAL",
                  wave_stage="ACTIVE")
    assert q.items["A"].state == "READY"
    assert q.ready() == ["A"]
    assert q.summary()["READY"] == 1


def test_queue_blocked_and_expired():
    q = OpportunityQueue()
    q.auto_update("B", permission="BLOCK", entry_timing="OPTIMAL")
    assert q.items["B"].state == "BLOCKED"
    q.auto_update("C", permission="ALLOW", entry_timing="OPTIMAL",
                  age_days=120, max_age_days=90)
    assert q.items["C"].state == "EXPIRED"
