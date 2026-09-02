# coding: utf-8
"""Time-in-Trade Governance 测试（16 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.time_in_trade import evaluate_time_in_trade


def test_hold_within_expected():
    t = evaluate_time_in_trade("2024-02-01", "2024-02-20",
                               expected_holding_days=45,
                               max_holding_days=90,
                               progress_since_entry=0.10)
    assert t.status == "HOLD"
    assert t.holding_days == 19


def test_reduce_over_expected_no_profit():
    t = evaluate_time_in_trade("2024-01-01", "2024-03-01",
                               expected_holding_days=45,
                               max_holding_days=90,
                               progress_since_entry=-0.02)
    assert t.status == "REDUCE"
    assert t.holding_days == 60


def test_exit_over_max_no_progress():
    t = evaluate_time_in_trade("2024-01-01", "2024-05-01",
                               expected_holding_days=45,
                               max_holding_days=90,
                               progress_since_entry=0.0)
    assert t.status == "EXIT"
    assert "MAX_HOLDING_EXCEEDED" in t.reasons


def test_reduce_over_max_with_progress():
    t = evaluate_time_in_trade("2024-01-01", "2024-05-01",
                               expected_holding_days=45,
                               max_holding_days=90,
                               last_confirmation_date="2024-04-28",
                               progress_since_entry=0.15)
    assert t.status == "REDUCE"


def test_stale_confirmation():
    t = evaluate_time_in_trade("2024-01-01", "2024-03-01",
                               expected_holding_days=60,
                               max_holding_days=120,
                               last_confirmation_date="2024-01-10",
                               progress_since_entry=0.10)
    assert t.status == "REDUCE"
    assert any(r.startswith("NO_CONFIRMATION_") for r in t.reasons)
