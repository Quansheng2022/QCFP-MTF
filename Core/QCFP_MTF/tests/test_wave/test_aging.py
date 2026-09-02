# coding: utf-8
"""Opportunity Aging Engine 测试（42 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.wave.aging import evaluate_opportunity_aging, opportunity_decay


def test_early_opportunity():
    a = evaluate_opportunity_aging(
        "w1", "01951", "2024-01-01", "2024-01-08",
        expected_mfe=0.20, realized_mfe=0.03)
    assert a.stage == "EARLY"
    assert a.entry_allowed is True
    assert a.max_entry_scale == 1.0


def test_late_opportunity_blocks_full_entry():
    a = evaluate_opportunity_aging(
        "w1", "01951", "2024-01-01", "2024-03-01",
        expected_mfe=0.20, realized_mfe=0.19)
    assert a.stage == "LATE"
    assert a.entry_allowed is False
    assert a.max_entry_scale == 0.0
    assert any("MFE_LARGELY_REALIZED" in r for r in a.reasons)


def test_mature_opportunity_scaled_entry():
    a = evaluate_opportunity_aging(
        "w1", "01951", "2024-01-01", "2024-02-01",
        expected_mfe=0.20, realized_mfe=0.12)
    assert a.stage == "MATURE"
    assert a.entry_allowed is True
    assert a.max_entry_scale == 0.5


def test_expired_by_age():
    a = evaluate_opportunity_aging(
        "w1", "01951", "2024-01-01", "2024-06-01",
        expected_mfe=0.20, realized_mfe=0.05, max_age_days=120)
    assert a.stage == "EXPIRED"
    assert a.entry_allowed is False


def test_opportunity_decay_62():
    d1 = opportunity_decay(age_days=0)
    d5 = opportunity_decay(age_days=5, half_life_days=5)
    d12 = opportunity_decay(age_days=12, half_life_days=5)
    assert d1["opportunity_value_pct"] == 100.0
    assert d5["opportunity_value_pct"] < 100.0
    assert d12["opportunity_value_pct"] < d5["opportunity_value_pct"]
    slow = opportunity_decay(5, momentum=0.8)
    fast = opportunity_decay(5, momentum=-0.8)
    assert slow["opportunity_value_pct"] > fast["opportunity_value_pct"]
