# coding: utf-8
"""Change Impact Matrix 测试（38 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.change_impact import (IMPACT_AREAS,
                                               assert_change_reviewed,
                                               change_impact_matrix)


def test_doc_change_low_impact():
    r = change_impact_matrix({"change_type": "doc",
                              "touches": ["Research-only"]})
    assert r["validation_requirement"] == "LOW"


def test_permission_change_full_validation():
    r = change_impact_matrix({"change_type": "rule",
                              "touches": ["Permission", "Risk"]})
    assert "Permission" in r["critical_touches"]
    assert r["validation_requirement"] == "FULL_VALIDATION"
    assert_change_reviewed(r)


def test_unreviewed_critical_rejected():
    r = change_impact_matrix({"change_type": "rule",
                              "touches": ["Permission"]})
    # 篡改 validation requirement → 应拒绝
    r["validation_requirement"] = "LOW"
    try:
        assert_change_reviewed(r)
        raise AssertionError("should raise")
    except ValueError:
        pass


def test_impact_areas():
    assert len(IMPACT_AREAS) == 10
    assert "Ledger" in IMPACT_AREAS
