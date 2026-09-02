# coding: utf-8
"""Universe 历史可投资状态测试（新 34 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.data.universe_snapshot import INVESTABILITY_STATES, \
    universe_investability_state, universe_snapshot_contract


def test_investability_states():
    assert universe_investability_state({"suspended": True}) == \
        "suspended"
    assert universe_investability_state(
        {"delisting_window": True}) == "delisting_window"
    assert universe_investability_state(
        {"corporate_action_locked": True}) == "corporate_action_locked"
    assert universe_investability_state({}) == "eligible"
    assert "new_listing" in INVESTABILITY_STATES


def test_snapshot_includes_investability():
    entries = [
        {"stock_code": "00700", "listed_date": "2000-01-01",
         "active": True},
        {"stock_code": "S01", "listed_date": "2020-01-01",
         "active": True, "suspended": True},
        {"stock_code": "D01", "listed_date": "2010-01-01",
         "delisted_date": "2023-06-30", "active": False},
    ]
    r = universe_snapshot_contract(entries, "2022-01-01")
    assert r["investability"]["00700"] == "eligible"
    assert r["investability"]["S01"] == "suspended"
    assert r["universe_snapshot_id"]
    assert r["n_stocks"] == 3
