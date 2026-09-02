# coding: utf-8
"""Institutional Permission Strength 测试（72 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.permission_gate import permission_strength, \
    permission_strength_cap


def test_permission_strength_values():
    assert permission_strength("BLOCK") == 0.0
    assert permission_strength("TEST") == 0.25
    assert permission_strength("LIMITED") == 0.50
    assert permission_strength("ALLOW") == 0.75
    assert permission_strength("STRONG_ALLOW") == 1.0


def test_strength_cap_only_lowers():
    # raw=8% × strength=0.5 → cap=4%（降低）
    r = permission_strength_cap(0.08, "LIMITED")
    assert r["permission_cap"] == 0.04
    assert r["final_cap"] == 0.04
    assert r["lowered"] is True
    # FULL_ALLOW → 不提高
    r2 = permission_strength_cap(0.08, "STRONG_ALLOW")
    assert r2["final_cap"] == 0.08
    assert r2["lowered"] is False


def test_strength_never_raises():
    # 即使输入 strength>1，cap 也 ≤ raw
    r = permission_strength_cap(0.08, "ALLOW", strength_input=1.5)
    assert r["final_cap"] <= 0.08
