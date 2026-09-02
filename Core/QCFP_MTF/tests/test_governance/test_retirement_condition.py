# coding: utf-8
"""Sunset Policy Retirement Condition 测试（新 95 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.sunset_policy import feature_sunset_eligibility, \
    retirement_condition_required


def test_no_retirement_condition_blocks_production():
    r = retirement_condition_required("WaveGate", "")
    assert r["verdict"] == "PRODUCTION_BLOCKED"
    assert r["production_allowed"] is False
    r2 = retirement_condition_required("WaveGate", "OOS 连续 2 期失败")
    assert r2["verdict"] == "RETIREMENT_CONDITION_PRESENT"


def test_sunset_eligibility():
    r = feature_sunset_eligibility("WaveGate",
                                   ["no_incremental_value",
                                    "repeated_oos_failure"])
    assert r["verdict"] == "ENTER_SUNSET"
    r2 = feature_sunset_eligibility("Permission", [])
    assert r2["verdict"] == "ACTIVE_CONTINUES"
