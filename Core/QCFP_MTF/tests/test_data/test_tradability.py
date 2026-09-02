# coding: utf-8
"""Tradability Governance 测试（35 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.data.tradability import tradability_status, \
    tradability_to_target


def test_normal():
    t = tradability_status(adv_amount=1e8)
    assert t["state"] == "NORMAL"
    assert t["tradable"] is True
    assert t["execution_cap_scale"] == 1.0


def test_suspended_blocked():
    t = tradability_status(suspended=True)
    assert t["state"] == "SUSPENDED"
    assert t["tradable"] is False
    r = tradability_to_target(0.2, t)
    assert r["tradable_target"] == 0.0
    assert r["blocked"] is True


def test_low_adv_no_liquidity():
    t = tradability_status(adv_amount=10000, min_adv=1e6)
    assert t["state"] == "NO_VOLUME"
    assert t["tradable"] is False


def test_corporate_action_scaled():
    t = tradability_status(corporate_action_pending=True)
    assert t["state"] == "CORPORATE_ACTION_PENDING"
    r = tradability_to_target(0.2, t)
    assert r["tradable_target"] == 0.06
