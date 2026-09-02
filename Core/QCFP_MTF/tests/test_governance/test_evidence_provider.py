# coding: utf-8
"""Evidence Provider 测试（P0-3 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.evidence_provider import Evidence, EvidenceProvider


def test_evidence_object():
    e = Evidence("pit", True, "ok")
    assert e.passed is True
    assert e.as_dict()["evidence_type"] == "pit"


def test_provider_verify_oos():
    p = EvidenceProvider()
    assert p.verify_oos(None).passed is False
    assert p.verify_oos(
        {"consistent": True, "positive_window_ratio": 0.8}).passed is True


def test_provider_verify_ablation():
    p = EvidenceProvider()
    assert p.verify_ablation(
        {"verdict": "INCREMENTAL_ALPHA"}).passed is True
    assert p.verify_ablation({"verdict": "NEUTRAL"}).passed is False


def test_bundle_rejects_manual_pass():
    p = EvidenceProvider()
    try:
        p.bundle({"ledger_ok": True})     # 手工声明 → 拒绝
        raise AssertionError("should raise")
    except TypeError:
        pass
    b = p.bundle({"pit": Evidence("pit", True, "ok")})
    assert b["pit"]["passed"] is True
