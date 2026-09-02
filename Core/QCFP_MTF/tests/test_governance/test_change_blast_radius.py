# coding: utf-8
"""Change Blast Radius 测试（新 38 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.change_impact import change_blast_radius, \
    decision_impact_report


def _change():
    return {
        "change_type": "permission_policy",
        "touches": ["Permission", "FinalTarget"],
        "description": "调整 Permission 上限",
        "affected_decisions": 182,
        "affected_reports": ["all_in_one"],
        "affected_replays": ["replay_2024"],
        "affected_certificates": ["cert_2024Q3"],
    }


def test_blast_radius():
    r = change_blast_radius(_change(), list(range(1000)),
                            {"ADD->HOLD": 51, "HOLD->REDUCE": 27})
    assert r["affected_ratio"] == 0.182
    assert r["decision_flips"]["ADD->HOLD"] == 51
    assert r["affected_reports"] == ["all_in_one"]
    assert r["validation_requirement"] == "FULL_VALIDATION"
    assert r["requires_decision_impact_report"] is True


def test_decision_impact_report_required():
    r = decision_impact_report(_change(), list(range(1000)))
    assert r["report"] == "DECISION_IMPACT_REPORT"
    assert r["required"] is True
