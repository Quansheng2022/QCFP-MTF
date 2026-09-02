# coding: utf-8
"""Evidence Expiry Policy 测试（82 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.evidence_expiry import evidence_expiry_policy


def _cert(expiry):
    return {
        "evidence_start": "2022-01", "evidence_end": "2024-12",
        "market_regimes_covered": ["Bull", "Bear"],
        "sample_size": 120, "certificate_expiry": expiry,
    }


def test_fresh_evidence():
    r = evidence_expiry_policy(_cert("2027-12"), as_of="2026-08")
    assert r["freshness"] == "FRESH"
    assert r["certification_status"] == "CERTIFIED"
    assert r["revalidation_required"] is False


def test_aging_evidence():
    r = evidence_expiry_policy(_cert("2026-10"), as_of="2026-08")
    assert r["freshness"] == "AGING"
    assert r["certification_status"] == "DOWNGRADED"
    assert r["revalidation_required"] is True


def test_expired_evidence():
    r = evidence_expiry_policy(_cert("2026-01"), as_of="2026-08")
    assert r["freshness"] == "EXPIRED"
    assert r["certification_status"] == "INSUFFICIENT"
    assert r["revalidation_required"] is True
    assert r["auto_param_modify_forbidden"] is True
    assert "Shadow" in r["chain"]
