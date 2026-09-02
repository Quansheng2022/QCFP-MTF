# coding: utf-8
"""UniverseSnapshot 增强测试（新 22 号：Survivorship + 可交易字段）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.data.universe_snapshot import universe_snapshot_contract


def _entries():
    return [
        {"stock_code": "00700", "listed_date": "2000-01-01",
         "active": True, "tradable": True, "board": "MAIN",
         "currency": "HKD", "lot_size": 100,
         "universe_reason": "liquid_mainboard"},
        {"stock_code": "OLD01", "listed_date": "2010-01-01",
         "delisted_date": "2023-06-30", "active": False,
         "tradable": False, "board": "MAIN", "currency": "HKD"},
    ]


def test_universe_includes_delisted_at_2022():
    r = universe_snapshot_contract(_entries(), "2022-01-01")
    assert "OLD01" in r["stocks"]           # 当时存在 → 不得排除
    assert "OLD01" in r["delisted_but_included"]
    assert r["survivorship_control"] is True


def test_universe_excludes_delisted_after():
    r = universe_snapshot_contract(_entries(), "2024-01-01")
    assert "OLD01" not in r["stocks"]


def test_tradability_fields_preserved():
    r = universe_snapshot_contract(_entries(), "2022-01-01")
    assert r["universe_snapshot_id"]
    assert r["n_stocks"] == 2
