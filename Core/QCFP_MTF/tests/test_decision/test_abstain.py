# coding: utf-8
"""ABSTAIN / NO_DECISION 语义测试（47 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.abstain import abstain_decision


def test_all_ok_is_hold():
    r = abstain_decision()
    assert r["decision"] == "HOLD"
    assert r["abstain"] is False
    assert r["reasons"] == []


def test_pit_unknown_is_no_decision():
    r = abstain_decision(pit_ok=False)
    assert r["decision"] == "NO_DECISION"
    assert r["abstain"] is True
    assert "PIT_UNKNOWN" in r["reasons"]


def test_multiple_missing_reasons():
    r = abstain_decision(pit_ok=True, replay_ok=False, ledger_ok=False)
    assert r["decision"] == "NO_DECISION"
    assert set(r["reasons"]) == {"REPLAY_FAILED", "LEDGER_INVALID"}


def test_certificate_missing_abstains():
    r = abstain_decision(certificate_ok=False)
    assert r["decision"] == "NO_DECISION"
    assert r["reasons"] == ["CERTIFICATE_MISSING"]
