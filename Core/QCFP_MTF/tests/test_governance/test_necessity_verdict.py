# coding: utf-8
"""Decision Necessity 资格审查测试（新 71 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.decision_necessity import necessity_verdict


def test_keep_unique_and_independent():
    r = necessity_verdict("Permission", "机构环境上限", covered_by=None,
                          independent_impact=0.08, oos_value=0.02)
    assert r["verdict"] == "KEEP"


def test_merge_when_covered():
    r = necessity_verdict("ChaseFilter", "防止追涨", covered_by="WaveMaturity",
                          independent_impact=0.04, oos_value=0.03)
    assert r["verdict"] == "MERGE"


def test_drop_no_independent_value():
    r = necessity_verdict("LegacyScore", "历史遗留", covered_by=None,
                          independent_impact=0.0, oos_value=0.0)
    assert r["verdict"] == "DROP"


def test_review_unprovable():
    r = necessity_verdict("X", "", covered_by=None,
                          independent_impact=0.0, oos_value=0.0)
    assert r["verdict"] == "REVIEW"
