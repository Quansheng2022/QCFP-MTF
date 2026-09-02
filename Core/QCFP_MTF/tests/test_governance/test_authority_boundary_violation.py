# coding: utf-8
"""Cross-Layer 权力边界测试（新 87 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.cross_layer_contradiction import \
    SEMANTIC_BOUNDARIES, authority_boundary_violation, semantic_boundaries


def test_four_semantic_boundaries():
    assert len(SEMANTIC_BOUNDARIES) == 4
    s = semantic_boundaries()
    assert "Opportunity ≠ Permission" in s["boundaries"]
    assert "Outcome ≠ Decision Quality" in s["boundaries"]


def test_boundary_ok():
    r = authority_boundary_violation({})
    assert r["verdict"] == "BOUNDARY_OK"


def test_violations_detected():
    r = authority_boundary_violation({
        "downstream_upgraded_permission": True,
        "report_rewrote_action": True,
        "execution_bypassed_final_target": True})
    assert r["verdict"] == "BOUNDARY_VIOLATION"
    assert set(r["violations"]) == {
        "DOWNSTREAM_UPGRADED_PERMISSION",
        "REPORT_REWROTE_ACTION",
        "EXECUTION_BYPASSED_FINAL_TARGET"}
