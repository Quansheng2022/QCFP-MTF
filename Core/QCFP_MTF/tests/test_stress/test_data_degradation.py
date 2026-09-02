# coding: utf-8
"""Data Degradation Simulator 测试（93 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.stress.data_degradation import data_degradation_simulator


def test_good_data():
    h = data_degradation_simulator(missing_rate=0.02)
    assert h.status == "GOOD"
    assert h.new_entry_allowed is True


def test_bad_data_blocks_new_entry():
    h = data_degradation_simulator(missing_rate=0.15)
    assert h.status == "BAD"
    assert h.new_entry_allowed is False
    assert "MISSING_RATE_HIGH" in h.degrade_reasons


def test_critical_errors_block():
    h = data_degradation_simulator(wrong_timestamp=True,
                                   corporate_action_error=True)
    assert h.status == "BAD"
    assert "WRONG_TIMESTAMP" in h.degrade_reasons
    assert "CORPORATE_ACTION_ERROR" in h.degrade_reasons


def test_degraded_delay():
    h = data_degradation_simulator(delay_minutes=10)
    assert h.status == "DEGRADED"
    assert h.new_entry_allowed is False
