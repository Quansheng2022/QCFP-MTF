# coding: utf-8
"""Dominated Rule Detection 测试（84 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.research.dominated_rule_detection import \
    dominated_rule_detection


def _stats():
    return {
        "PermissionCap": {"triggered": 200, "binding": 40,
                          "independently_changed": 10,
                          "prevented_violation": 5},
        "WaveGate": {"triggered": 120, "binding": 0,
                     "independently_changed": 30,
                     "prevented_violation": 0},
        "LegacyCap": {"triggered": 80, "binding": 0,
                      "independently_changed": 0,
                      "prevented_violation": 0},
        "DeadRule": {"triggered": 0, "binding": 0,
                     "independently_changed": 0,
                     "prevented_violation": 0},
    }


def test_classification():
    r = dominated_rule_detection(_stats())
    assert r["results"]["PermissionCap"]["classification"] == "ESSENTIAL"
    assert r["results"]["WaveGate"]["classification"] == "USEFUL"
    assert r["results"]["LegacyCap"]["classification"] == "DOMINATED"
    assert r["results"]["DeadRule"]["classification"] == "REDUNDANT"


def test_retire_candidates():
    r = dominated_rule_detection(_stats())
    assert "LegacyCap" in r["retire_candidates"]
    assert "DeadRule" in r["retire_candidates"]
    assert "PermissionCap" not in r["retire_candidates"]
