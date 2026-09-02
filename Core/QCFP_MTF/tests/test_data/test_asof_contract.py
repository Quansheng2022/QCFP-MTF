# coding: utf-8
"""AsOfTimeContract 测试（33 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.data.asof_contract import (TIME_ROLES, asof_time_contract,
                                         assert_asof_time_valid)
from QCFP_MTF.governance.feature_gate import FeatureGateError


def test_asof_valid():
    ev = {"available_time": "2026-08-21", "decision_time": "2026-08-21",
          "execution_time": "2026-08-22", "outcome_time": "2026-08-29"}
    r = asof_time_contract(ev, "2026-08-21")
    assert r["pit_valid"] is True
    assert_asof_time_valid(ev, "2026-08-21")


def test_pit_violation():
    ev = {"available_time": "2026-08-25"}
    r = asof_time_contract(ev, "2026-08-21")
    assert r["pit_valid"] is False
    assert any("PIT" in v for v in r["violations"])
    try:
        assert_asof_time_valid(ev, "2026-08-21")
        raise AssertionError("should raise")
    except FeatureGateError:
        pass


def test_time_roles():
    assert TIME_ROLES == ("observation_time", "period_end",
                          "source_publish_time", "system_available_time",
                          "available_time", "decision_time",
                          "execution_time", "outcome_time")
