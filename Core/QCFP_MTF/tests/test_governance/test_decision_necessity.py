# coding: utf-8
"""Decision Necessity Audit 测试（71 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.decision_necessity import decision_necessity_audit, \
    necessity_summary


def _modules():
    return {
        "Permission": {
            "purpose": "机构环境上限",
            "independent_value": "唯一决定权限上限",
            "failure_if_removed": "信号可越权",
            "current_evidence": "Ablation A1 降 MDD 10pp",
        },
        "LegacyScore": {
            "purpose": "历史遗留评分",
            "covered_by": "Permission",
        },
    }


def test_necessity_audit():
    r = decision_necessity_audit(_modules())
    assert r["results"]["Permission"]["verdict"] == "JUSTIFIED"
    assert r["results"]["LegacyScore"]["verdict"] == "REVIEW"
    assert r["justified"] == 1
    assert r["review"] == 1


def test_necessity_summary():
    r = decision_necessity_audit(_modules())
    s = necessity_summary(r)
    assert "LegacyScore" in s["review_modules"]
    assert s["justified_ratio"] == 0.5


def test_missing_evidence_review():
    r = decision_necessity_audit({"X": {"purpose": "唯一"}})
    assert r["results"]["X"]["verdict"] == "REVIEW"
    assert "current_evidence" in r["results"]["X"]["missing"]
