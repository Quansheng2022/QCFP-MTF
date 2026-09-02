# coding: utf-8
"""Tradability 唯一权威测试（新 35 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.data.tradability import TRADABILITY_STATES, \
    tradability_authority, tradability_status


def test_single_authority_states():
    assert set(TRADABILITY_STATES) == {
        "NORMAL", "SUSPENDED", "HALTED", "NO_VOLUME",
        "CORPORATE_ACTION_PENDING", "DELISTING", "NOT_ELIGIBLE"}


def test_authority_never_increases():
    for state in TRADABILITY_STATES:
        a = tradability_authority(state)
        assert a["execution_cap_scale"] <= 1.0
        assert a["authority"] == "TRADABILITY_AUTHORITY"
    assert tradability_authority("NORMAL")["execution_cap_scale"] == 1.0
    assert tradability_authority("NO_VOLUME")["tradable"] is False


def test_status_uses_authority():
    r = tradability_status(delisting=True)
    assert r["state"] == "DELISTING"
    assert r["execution_cap_scale"] == 0.0
    assert r["tradable"] is False
