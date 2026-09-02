# coding: utf-8
"""Sunset Policy 测试（95 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.sunset_policy import SUNSET_LIFECYCLE, \
    advance_sunset, sunset_policy


def test_active_when_no_trigger():
    r = sunset_policy("WaveGate", [])
    assert r["state"] == "ACTIVE"


def test_single_trigger_review_due():
    r = sunset_policy("WaveGate", ["evidence_expired"])
    assert r["state"] == "REVIEW_DUE"


def test_multiple_triggers_sunset_candidate():
    r = sunset_policy("WaveGate", ["no_incremental_value",
                                   "never_binding"])
    assert r["state"] == "SUNSET_CANDIDATE"


def test_repeated_oos_failure_shadow_only():
    r = sunset_policy("WaveGate", ["repeated_oos_failure",
                                   "evidence_expired"])
    assert r["state"] == "SHADOW_ONLY"


def test_advance_forward_only():
    assert advance_sunset("ACTIVE", "RETIRED") == "RETIRED"
    try:
        advance_sunset("RETIRED", "ACTIVE")
        raise AssertionError("should raise")
    except ValueError:
        pass


def test_lifecycle_order():
    assert SUNSET_LIFECYCLE == ("ACTIVE", "REVIEW_DUE",
                                "SUNSET_CANDIDATE", "SHADOW_ONLY",
                                "RETIRED")
