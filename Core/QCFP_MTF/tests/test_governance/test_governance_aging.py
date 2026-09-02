# coding: utf-8
"""Governance Aging Review 测试（81 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.governance_aging import governance_aging_review


def _rules():
    return {
        "PermissionPolicy": {
            "certified_at": "2026-03",
            "last_revalidated_at": "2026-08",
            "evidence_window": "2024-01..2026-06",
        },
        "WaveStagePolicy": {
            "certified_at": "2024-09",
            "last_revalidated_at": "2025-06",
            "evidence_window": "2022-01..2024-06",
        },
        "LiquidityAssumption": {
            "certified_at": "2023-01",
            "last_revalidated_at": "2023-01",
            "evidence_window": "2021-01..2022-12",
        },
    }


def test_aging_statuses():
    r = governance_aging_review(_rules(), as_of="2026-08")
    assert r["results"]["PermissionPolicy"]["current_status"] == "ACTIVE"
    assert r["results"]["WaveStagePolicy"]["current_status"] == \
        "REVALIDATE"
    assert r["results"]["LiquidityAssumption"]["current_status"] == \
        "RETIRE"


def test_next_review_due():
    r = governance_aging_review(_rules(), as_of="2026-08")
    assert r["results"]["PermissionPolicy"]["next_review_due"] == "2027-08"
    assert r["results"]["PermissionPolicy"]["months_since_revalidation"] == 0


def test_age_boundary():
    r = governance_aging_review(
        {"X": {"certified_at": "2025-08",
               "last_revalidated_at": "2025-08"}},
        as_of="2026-08")
    assert r["results"]["X"]["current_status"] == "REVALIDATE"
