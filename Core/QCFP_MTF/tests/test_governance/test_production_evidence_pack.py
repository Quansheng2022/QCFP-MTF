# coding: utf-8
"""Production Evidence Pack 测试（91 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.production_evidence_pack import \
    EVIDENCE_PACK_FIELDS, production_evidence_pack, \
    trace_decision_to_evidence


def _evidence():
    return {f: f"-ref" for f in EVIDENCE_PACK_FIELDS}


def test_complete_pack_certified():
    p = production_evidence_pack("REL-001", _evidence())
    assert p["certified"] is True
    assert p["certification"] == "CERTIFIED"
    assert p["evidence_hash"]
    assert len(p["components"]) == len(EVIDENCE_PACK_FIELDS)


def test_missing_pack_not_certified():
    evidence = _evidence()
    del evidence["governance_approval"]
    p = production_evidence_pack("REL-002", evidence)
    assert p["certified"] is False
    assert p["certification"] == "NOT_CERTIFIED"
    assert p["missing"] == ["governance_approval"]


def test_trace_decision_to_evidence():
    p = production_evidence_pack("REL-001", _evidence())
    t = trace_decision_to_evidence("D-1", "REL-001", p)
    assert t["traceable"] is True
    assert t["evidence_hash"] == p["evidence_hash"]
    assert t["certification"] == "CERTIFIED"
