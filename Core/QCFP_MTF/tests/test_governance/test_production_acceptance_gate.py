# coding: utf-8
"""Production Acceptance 总闸测试（新 51 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.production_acceptance import \
    PRODUCTION_ACCEPTANCE_GATES, production_acceptance_contract, \
    production_acceptance_gate


def _accept(verdict="ACCEPTED"):
    gates = {g: {"ok": True} for g in PRODUCTION_ACCEPTANCE_GATES}
    if verdict == "REJECTED":
        gates["GOVERNANCE"] = {"ok": False}
    return production_acceptance_contract(gates)


def test_rejected_release_zero_certified():
    r = production_acceptance_gate(_accept("REJECTED"),
                                    release_verdict="REJECTED",
                                    certified_decisions=["d1"])
    assert r["verdict"] == "GATE_VIOLATION"
    assert r["violation"] is True


def test_accepted_release_allows_certified():
    r = production_acceptance_gate(_accept("ACCEPTED"),
                                    release_verdict="ACCEPTED",
                                    certified_decisions=["d1"])
    assert r["verdict"] == "GATE_OK"


def test_rejected_with_zero_certified_ok():
    r = production_acceptance_gate(_accept("REJECTED"),
                                    release_verdict="REJECTED",
                                    certified_decisions=[])
    assert r["verdict"] == "GATE_OK"
    assert r["certified_decision_count"] == 0
