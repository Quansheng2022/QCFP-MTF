# coding: utf-8
"""PermissionPolicy 唯一权限语义测试（Release 2：新 11 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.permission_gate import PermissionGateError, \
    assert_permission_upper_bound
from QCFP_MTF.decision.permission_policy import PermissionPolicy


def test_block_progressive_derisk_allowed():
    """BLOCK + previous=30% → final <30% 不要求立即=0。"""
    assert_permission_upper_bound("BLOCK", 0.20, previous_position=0.30)
    try:
        assert_permission_upper_bound("BLOCK", 0.40, previous_position=0.30)
        raise AssertionError("should raise")
    except PermissionGateError:
        pass


def test_block_hard_exit_zero():
    try:
        assert_permission_upper_bound("BLOCK", 0.20, previous_position=0.30,
                                      exit_severity=3)
        raise AssertionError("should raise")
    except PermissionGateError:
        pass


def test_policy_single_source():
    p = PermissionPolicy.from_permission("BLOCK", exit_severity=0)
    assert p.derisk_mode == "PROGRESSIVE"
    assert p.maintain_allowed is False
    p2 = PermissionPolicy.from_permission("BLOCK", exit_severity=3)
    assert p2.derisk_mode == "IMMEDIATE_EXIT"


def test_governance_matrix_previous_context():
    from QCFP_MTF.decision.governance import governance_matrix_ok
    ok, reasons = governance_matrix_ok("BLOCK", "BREAKOUT", "Low", 0.20,
                                       previous_position=0.30)
    assert ok is True
    ok2, r2 = governance_matrix_ok("BLOCK", "BREAKOUT", "Low", 0.20)
    assert ok2 is False   # 无 previous 上下文 → 严格判违规
    assert "BLOCK_TARGET_NONZERO" in r2
