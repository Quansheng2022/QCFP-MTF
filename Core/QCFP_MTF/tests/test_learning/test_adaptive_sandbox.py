# coding: utf-8
"""Adaptive Policy Sandbox 测试（69 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.learning.adaptive_sandbox import (AdaptiveSandbox,
                                                SandboxGuardError)


def _gates():
    return {"backtest": True, "oos": True, "ablation": True,
            "stress": True, "replay": True, "release_gate": True}


def test_production_cannot_read_experimental():
    sb = AdaptiveSandbox()
    sb.propose("POLICY-1", {"threshold": 0.6})
    try:
        sb.get_certified_policy("POLICY-1")
        raise AssertionError("should raise")
    except SandboxGuardError:
        pass


def test_certify_and_read():
    sb = AdaptiveSandbox()
    sb.propose("POLICY-1", {"threshold": 0.6})
    p = sb.certify("POLICY-1", _gates())
    assert p.status == "certified"
    assert sb.get_certified_policy("POLICY-1").params == {"threshold": 0.6}


def test_certify_requires_gates():
    sb = AdaptiveSandbox()
    sb.propose("POLICY-2", {})
    try:
        sb.certify("POLICY-2", {"oos": True})
        raise AssertionError("should raise")
    except SandboxGuardError:
        pass


def test_latest_certified():
    sb = AdaptiveSandbox()
    sb.propose("P1", {"a": 1})
    sb.certify("P1", _gates())
    sb.propose("P2", {"a": 2})
    sb.certify("P2", _gates())
    assert sb.get_certified_policy().policy_id == "P2"
