# coding: utf-8
"""PermissionPolicy 唯一化测试（新 3 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.permission_policy import PermissionPolicy, \
    permission_derisk_mode, permission_policy_object


def test_block_progressive_derisk():
    p = PermissionPolicy.from_permission("BLOCK")
    assert p.new_risk_allowed is False
    assert p.add_allowed is False
    assert p.mandatory_derisk is True
    assert p.derisk_mode == "PROGRESSIVE"
    assert p.max_new_risk == 0.0


def test_hard_exit_immediate_derisk():
    p = PermissionPolicy.from_permission("BLOCK", exit_severity=3)
    assert p.derisk_mode == "IMMEDIATE_EXIT"
    assert permission_derisk_mode("BLOCK", hard_exit=True) == \
        "IMMEDIATE_EXIT"


def test_allow_no_derisk():
    p = PermissionPolicy.from_permission("ALLOW")
    assert p.derisk_mode == "NONE"
    assert p.new_risk_allowed is True
    assert p.add_allowed is True


def test_policy_object_has_derisk_fields():
    pol = permission_policy_object("BLOCK")
    assert pol["derisk_mode"] == "PROGRESSIVE"
    assert pol["max_new_risk"] == 0.0
    assert permission_policy_object("TEST")["max_new_risk"] == 0.20
