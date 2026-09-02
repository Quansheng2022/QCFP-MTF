# coding: utf-8
"""Dominated Rule → 删除测试入口测试（新 84 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.research.dominated_rule_detection import \
    dominated_rule_detection, dominated_to_removal


def _stats():
    return {
        "PermissionCap": {"triggered": 200, "binding": 40,
                          "independently_changed": 10,
                          "prevented_violation": 5},
        "LegacyCap": {"triggered": 80, "binding": 0,
                      "independently_changed": 0,
                      "prevented_violation": 0},
        "DeadRule": {"triggered": 0, "binding": 0,
                     "independently_changed": 0,
                     "prevented_violation": 0},
    }


def test_redundant_dominated_enter_removal():
    d = dominated_rule_detection(_stats())
    r = dominated_to_removal(d)
    assert "LegacyCap" in r["removal_candidates"]
    assert "DeadRule" in r["removal_candidates"]
    assert "PermissionCap" not in r["removal_candidates"]
    assert r["feeds_rule_removal_test"] is True
