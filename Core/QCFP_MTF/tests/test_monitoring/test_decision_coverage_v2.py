# coding: utf-8
"""Decision Coverage 扩展测试（新 27 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.monitoring.decision_coverage import COVERAGE_STATES, \
    decision_coverage


def test_no_trade_state_included():
    counts = {"certified": 72, "no_trade": 16, "safe_mode": 5,
              "abstain": 6, "halted": 1}
    r = decision_coverage(counts)
    assert r["total_decisions"] == 100
    assert r["coverage"]["certified"] == 0.72
    assert r["coverage"]["no_trade"] == 0.16
    assert r["coverage"]["halted"] == 0.01
    assert "no_trade" in COVERAGE_STATES


def test_reason_breakdown_extended():
    counts = {"certified": 90, "no_trade": 4, "safe_mode": 0,
              "abstain": 5, "halted": 1}
    reasons = {"pit_unknown": 1, "no_wave": 2, "permission_block": 1,
               "liquidity_fail": 1, "data_missing": 0,
               "evidence_missing": 0, "permission_unavailable": 0,
               "liquidity_unavailable": 0, "replay_failure": 0}
    r = decision_coverage(counts, reasons)
    assert r["abstain_reason_breakdown"]["no_wave"] == 0.02
    assert r["abstain_reason_breakdown"]["permission_block"] == 0.01
    assert r["abstain_reason_breakdown"]["liquidity_fail"] == 0.01
