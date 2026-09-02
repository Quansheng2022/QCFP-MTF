# coding: utf-8
"""Change Impact Release Gate 测试（新 15 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.change_impact import change_impact_matrix, \
    change_impact_release_gate


def _critical_impact():
    return change_impact_matrix({
        "change_type": "permission_policy",
        "touches": ["Permission", "FinalTarget"],
        "description": "调整 Permission 上限"})


def test_critical_change_requires_full_validation():
    impact = _critical_impact()
    assert impact["validation_requirement"] == "FULL_VALIDATION"


def test_release_gate_blocks_without_evidence():
    impact = _critical_impact()
    r = change_impact_release_gate([impact], full_validation_evidence={})
    assert r["promotion"] == "FAIL"
    assert r["verdict"] == "RELEASE_GATE_FAIL"
    assert r["blocked"][0]["missing_evidence"] != []


def test_release_gate_passes_with_evidence():
    impact = _critical_impact()
    evidence = {"pit": True, "oos": True, "ablation": True,
                "replay": True, "shadow": True}
    r = change_impact_release_gate([impact], evidence)
    assert r["promotion"] == "ALLOW"
    assert r["blocked"] == []


def test_non_critical_change_not_blocked():
    impact = change_impact_matrix({
        "change_type": "report_wording",
        "touches": ["Report"],
        "description": "修改报告措辞"})
    r = change_impact_release_gate([impact])
    assert r["promotion"] == "ALLOW"
