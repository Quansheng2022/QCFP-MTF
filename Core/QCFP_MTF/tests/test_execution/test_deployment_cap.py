# coding: utf-8
"""DeploymentCap 只减权测试（Sprint 3 + Runtime Evidence Wiring）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.execution.deployment_cap import assert_deployment_invariant, \
    deployment_cap_authority_boundary, deployment_target


def test_deployment_target_capped():
    r = deployment_target(0.30, 0.05)
    assert r["deployment_target"] == 0.05
    assert r["canonical_target"] == 0.30
    assert r["invariant_ok"] is True
    assert assert_deployment_invariant(r)["verdict"] == "DEPLOYMENT_OK"


def test_cap_never_increases():
    r = deployment_target(0.10, 0.50)
    assert r["deployment_target"] == 0.10


def test_hard_exit_not_blocked():
    r = deployment_target(0.0, 0.05)
    assert r["deployment_target"] == 0.0


def test_cap_cannot_change_decision():
    r = deployment_cap_authority_boundary(
        {"permission": "ALLOW", "cap": 0.05})
    assert r["violation"] is True
    r2 = deployment_cap_authority_boundary({"cap": 0.05})
    assert r2["violation"] is False


def test_negative_cap_invalid():
    """第 7 项：负 Cap 必须 INVALID，不能靠 min() 数学上放行。"""
    r = deployment_target(0.30, -0.10)
    assert r["valid"] is False
    assert r["reason"] == "INVALID_DEPLOYMENT_CAP"
    assert r["deployment_target"] is None
    # 负 canonical target 同样非法
    r2 = deployment_target(-0.1, 0.05)
    assert r2["valid"] is False
    assert r2["reason"] == "INVALID_CANONICAL_TARGET"


def test_cap_above_approved_max_invalid():
    """第 7 项：Cap 不能超过 Governance 批准的 approved_max。"""
    r = deployment_target(0.30, 0.20, approved_max=0.10)
    assert r["valid"] is False
    assert r["reason"] == "INVALID_DEPLOYMENT_CAP"


def test_no_executed_target_field():
    """第 7 项：Deployment 层不产生 executed_target——
    ActualFill/Executed 只能来自 Runtime Event/Broker。"""
    r = deployment_target(0.30, 0.05)
    assert "executed_target" not in r
