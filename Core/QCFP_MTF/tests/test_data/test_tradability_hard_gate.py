# coding: utf-8
"""Tradability Execution Hard Gate 测试（新 23 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.data.tradability import tradability_hard_gate, \
    tradability_status


def test_delisting_blocks():
    r = tradability_hard_gate(0.3, tradability_status(delisting=True))
    assert r["blocked"] is True
    assert r["executable_target"] == 0.0
    assert r["tradability_state"] == "DELISTING"


def test_not_tradable_blocks():
    r = tradability_hard_gate(0.3, tradability_status(not_tradable=True))
    assert r["blocked"] is True
    assert r["tradability_state"] == "NOT_ELIGIBLE"


def test_corporate_action_reduces_not_raises():
    r = tradability_hard_gate(0.3, tradability_status(
        corporate_action_pending=True))
    assert r["blocked"] is False
    assert r["executable_target"] < r["proposal_target"]
    # 只能降低/阻止，绝不能提高
    assert r["executable_target"] <= r["proposal_target"]


def test_normal_full_execution():
    r = tradability_hard_gate(0.3, tradability_status())
    assert r["executable_target"] == 0.3
    assert r["blocked"] is False
