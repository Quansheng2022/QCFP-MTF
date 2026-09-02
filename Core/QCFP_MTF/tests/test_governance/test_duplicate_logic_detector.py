# coding: utf-8
"""Duplicate Logic Detector 测试（73 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.duplicate_logic_detector import \
    duplicate_logic_detector, duplicate_scan


def test_duplicate_pattern_warns():
    r = duplicate_logic_detector({
        "permission_block_condition": ["permission_policy.py",
                                       "engine.py", "report.py"],
        "unique_check": ["governance.py"],
    })
    assert r["ci_verdict"] == "WARN"
    assert "permission_block_condition" in r["duplicates"]
    assert r["duplicate_count"] == 1


def test_no_duplicate_passes():
    r = duplicate_logic_detector({
        "position_cap_calc": ["governance.py"],
        "action_mapping": ["action_gate.py"]})
    assert r["ci_verdict"] == "PASS"
    assert r["duplicate_count"] == 0


def test_duplicate_scan_groups_items():
    r = duplicate_scan([
        {"pattern": "if_permission_block", "module": "a.py"},
        {"pattern": "if_permission_block", "module": "b.py"},
        {"pattern": "unique", "module": "c.py"},
    ])
    assert "if_permission_block" in r["duplicates"]
    assert r["duplicate_count"] == 1
