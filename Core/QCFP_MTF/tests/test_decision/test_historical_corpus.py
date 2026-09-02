# coding: utf-8
"""Historical Integrity Corpus 测试（Release 3：新 22 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.historical_integrity import \
    HISTORICAL_INTEGRITY_CORPUS, historical_integrity_corpus_check


def _case():
    return {"evidence_snapshot_id": "E1", "release_id": "REL-1",
            "decision_hash": "H1", "final_target": 0.1,
            "action": "ENTRY", "binding_constraint": "liquidity_cap",
            "ledger_hash": "L1"}


def test_corpus_protected():
    cases = {c: dict(_case()) for c in HISTORICAL_INTEGRITY_CORPUS}
    r = historical_integrity_corpus_check(cases)
    assert r["verdict"] == "HISTORY_PROTECTED"
    assert r["silent_mutation_count"] == 0


def test_silent_mutation_detected():
    cases = {c: dict(_case()) for c in HISTORICAL_INTEGRITY_CORPUS}
    cases["bull"]["silently_mutated"] = True
    r = historical_integrity_corpus_check(cases)
    assert r["verdict"] == "HISTORY_MUTATED"
    assert r["silent_mutation_count"] == 1


def test_missing_fields_detected():
    cases = {c: dict(_case()) for c in HISTORICAL_INTEGRITY_CORPUS}
    del cases["crash"]["decision_hash"]
    r = historical_integrity_corpus_check(cases)
    assert r["silent_mutation_count"] == 1
    assert r["silent_mutations"][0]["case"] == "crash"
