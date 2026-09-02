# coding: utf-8
"""Evidence Hierarchy 生命周期绑定测试（新 93 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.research.evidence_hierarchy import active_feature_evidence_required, \
    evidence_level_lifecycle


def test_lifecycle_by_level():
    assert evidence_level_lifecycle(0)["lifecycle"] == "HYPOTHESIS"
    assert evidence_level_lifecycle(2)["lifecycle"] == "CANDIDATE"
    assert evidence_level_lifecycle(3)["lifecycle"] == "SHADOW_CANDIDATE"
    assert evidence_level_lifecycle(4)["lifecycle"] == "PRODUCTION_ELIGIBLE"
    assert evidence_level_lifecycle(6)["lifecycle"] == \
        "SUSTAINING_CERTIFICATION"


def test_active_requires_evidence_level():
    r = active_feature_evidence_required("NewAlpha", None)
    assert r["verdict"] == "RESEARCH_ONLY"
    assert r["production_allowed"] is False
    r2 = active_feature_evidence_required("NewAlpha", 4)
    assert r2["verdict"] == "ACTIVE_OK"
