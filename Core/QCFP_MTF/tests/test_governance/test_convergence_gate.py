# coding: utf-8
"""Convergence Release Gate 测试（Convergence 新 10 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.convergence_release import convergence_release_gate, \
    module_classification_gate


def test_module_classification():
    assert module_classification_gate("Permission", "PERMISSION")[
        "classification"] == "ACTIVE_CORE"
    r = module_classification_gate("TraceHelper", "SUB_CAPABILITY",
                                   necessity_proven=True)
    assert r["classification"] == "ACTIVE_SUBCAPABILITY"
    r2 = module_classification_gate("Orphan", "")
    assert r2["classification"] == "RETIRED"
    assert r2["production"] is False


def test_convergence_gate_pass():
    r = convergence_release_gate({
        "canonical_semantics": True, "fail_closed": True,
        "fact_integrity": True, "research_authority": True,
        "convergence": True})
    assert r["verdict"] == "CONVERGENCE_PASS"
    assert r["allowed"] is True


def test_convergence_gate_blocked():
    r = convergence_release_gate({
        "canonical_semantics": True, "fail_closed": False,
        "fact_integrity": True, "research_authority": True,
        "convergence": False})
    assert r["verdict"] == "CONVERGENCE_BLOCKED"
    assert "fail_closed" in r["failures"]
