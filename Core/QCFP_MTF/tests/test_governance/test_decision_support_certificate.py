# coding: utf-8
"""Decision Support Qualification Certificate 测试（P1-8）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.decision_support_certificate import \
    build_decision_support_certificate


def _base(**kw):
    return {
        "release_id": "REL-A", "evidence_freeze_id": "EF-1",
        "shadow": {"state": "SHADOW_QUALIFIED", "qualified_days": 20,
                   "required_days": 20},
        "outcome": {"outcome_qualified_days": 20, "required_days": 20},
        "replay": {"ok": True, "state": "REPLAY_ACCUMULATION_OK",
                   "stats": {"window_exact_rate": 1.0,
                             "replay_gap_days": []}},
        "violations": {"pit": 0, "permission": 0, "duplicate": 0,
                       "incident_escaped": 0},
        "oos_status": "OOS_PASS",
        "qualified": True,
        **kw,
    }


def test_certificate_qualified_with_oos():
    c = build_decision_support_certificate(**_base())
    assert c["certificate_status"] == "QUALIFIED"
    assert c["certificate_id"]
    assert c["schema"] == "DECISION-SUPPORT-CERTIFICATE-1"


def test_certificate_not_qualified_when_oos_pending_strict():
    """OOS 默认硬门：OOS_NOT_COMPARABLE → NOT_QUALIFIED（诚实）。"""
    c = build_decision_support_certificate(
        **_base(oos_status="OOS_NOT_COMPARABLE"))
    assert c["certificate_status"] == "NOT_QUALIFIED"
    assert c["oos_status"] == "OOS_NOT_COMPARABLE"


def test_certificate_with_oos_pending_opt_in():
    c = build_decision_support_certificate(
        **_base(oos_status="OOS_NOT_COMPARABLE", allow_oos_pending=True))
    assert c["certificate_status"] == "QUALIFIED_WITH_OOS_PENDING"


def test_certificate_suspended_on_hard_reset():
    c = build_decision_support_certificate(
        **_base(shadow={"state": "SUSPENDED", "qualified_days": 3,
                       "required_days": 20}))
    assert c["certificate_status"] == "SUSPENDED"


def test_certificate_not_qualified_when_shadow_accumulating():
    c = build_decision_support_certificate(
        **_base(shadow={"state": "SHADOW_ACCUMULATING",
                       "qualified_days": 17, "required_days": 20}))
    assert c["certificate_status"] == "NOT_QUALIFIED"
