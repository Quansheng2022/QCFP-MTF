# coding: utf-8
"""Unified PermissionPolicy 测试（P0-2 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.permission_policy import permission_policy_object


def test_block_semantics_unified():
    p = permission_policy_object("BLOCK")
    assert p["new_risk_allowed"] is False
    assert p["add_allowed"] is False
    assert p["maintain_allowed"] is False
    assert p["mandatory_derisk"] is True
    assert p["max_target"] == 0.0


def test_watch_observation():
    p = permission_policy_object("WATCH")
    assert p["new_risk_allowed"] is False
    assert p["add_allowed"] is False
    assert p["maintain_allowed"] is True
    assert p["observation_allowed"] is True


def test_allow_add():
    p = permission_policy_object("ALLOW")
    assert p["new_risk_allowed"] is True
    assert p["add_allowed"] is True
    assert p["max_target"] == 0.50


def test_test_no_add():
    p = permission_policy_object("TEST")
    assert p["new_risk_allowed"] is True
    assert p["add_allowed"] is False
