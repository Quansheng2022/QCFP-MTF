# coding: utf-8
"""Evidence Pack 写入 Ledger 测试（新 91 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.production_evidence_pack import \
    decision_qualification_answer, evidence_pack_ledger_binding


def test_ledger_binding_certified():
    r = evidence_pack_ledger_binding("d1", "REL-1",
                                     {"evidence_hash": "H1"})
    assert r["writable"] is True
    assert r["ledger_record"]["certification"] == "CERTIFIED"
    assert r["ledger_record"]["evidence_pack_id"] == "H1"


def test_qualification_answer_certified():
    r = decision_qualification_answer("d1", "REL-1",
                                      {"evidence_hash": "H1"})
    assert r["qualification"] == "CERTIFIED"
    assert "decision → release → evidence pack" in r["chain"]


def test_qualification_not_certified_without_pack():
    r = decision_qualification_answer("d1", "", {})
    assert r["qualification"] == "NOT_CERTIFIED"
    assert "无法反查" in r["reason"]
