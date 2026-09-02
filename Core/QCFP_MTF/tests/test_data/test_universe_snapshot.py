# coding: utf-8
"""UniverseSnapshotContract 测试（34 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.data.universe_snapshot import universe_snapshot_contract


def test_universe_snapshot():
    entries = [
        {"stock_code": "01951", "listed_date": "2019-01-01",
         "delisted_date": "", "active": True},
        {"stock_code": "00700", "listed_date": "2004-06-16",
         "delisted_date": "", "active": True},
        {"stock_code": "OLD", "listed_date": "2018-01-01",
         "delisted_date": "2023-06-30", "active": False},  # 已退市
        {"stock_code": "NEW", "listed_date": "2024-01-01",
         "delisted_date": "", "active": True},
    ]
    r = universe_snapshot_contract(entries, "2022-03-31")
    assert "OLD" in r["stocks"]          # 当时存在（今日已退市）→ 不排除
    assert "NEW" not in r["stocks"]      # 当时未上市 → 排除
    assert r["survivorship_control"] is True
    assert r["universe_snapshot_id"]
