# coding: utf-8
"""Golden Corpus Release Gate 测试（Release 2：新 14 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.golden_decision_corpus import golden_release_gate


def test_all_changes_explained_release_ok():
    r = golden_release_gate([
        {"case_id": "G_BLOCK", "changed": True,
         "approved_reason": "Permission 语义统一为渐进去风险"},
        {"case_id": "G_ALLOW", "changed": False}])
    assert r["verdict"] == "RELEASE_OK"
    assert r["allowed"] is True


def test_unexplained_change_blocks():
    r = golden_release_gate([
        {"case_id": "G_WAVE", "changed": True, "approved_reason": ""}])
    assert r["verdict"] == "GOLDEN_CHANGE_UNEXPLAINED"
    assert r["allowed"] is False
    assert r["unexplained_changes"] == ["G_WAVE"]
