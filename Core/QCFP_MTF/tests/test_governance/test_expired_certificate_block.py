# coding: utf-8
"""Evidence Expiry 绑定 Release 测试（新 82 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.evidence_expiry import evidence_expiry_policy, \
    evidence_pack_certificate_valid, expired_certificate_block


def _cert(expiry):
    return {"evidence_start": "2022-01", "evidence_end": "2024-12",
            "market_regimes_covered": ["Bull"],
            "sample_size": 120, "certificate_expiry": expiry}


def test_expired_blocks_release():
    r = expired_certificate_block(evidence_expiry_policy(
        _cert("2026-01"), as_of="2026-08"), release_id="REL-2")
    assert r["verdict"] == "RELEASE_BLOCKED"
    assert r["allowed"] is False


def test_fresh_certificate_allows():
    r = expired_certificate_block(evidence_expiry_policy(
        _cert("2027-12"), as_of="2026-08"), release_id="REL-2")
    assert r["verdict"] == "RELEASE_OK"


def test_pack_invalid_with_expired_certificate():
    r = evidence_pack_certificate_valid(
        {"evidence_hash": "H1"}, _cert("2026-01"))
    assert r["valid"] is False
    assert r["verdict"] == "EVIDENCE_PACK_EXPIRED"
