# coding: utf-8
"""PIT Universe Registry 测试（P0-5 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.data.pit_registry import (PitUniverseEntry,
                                        PitUniverseRegistry,
                                        pit_integrity_score,
                                        snapshot_hash)


def test_registry_stocks_known_at():
    reg = PitUniverseRegistry()
    reg.register(PitUniverseEntry("U1", "01951", "2024-01-01",
                                  effective_to="2024-06-30"))
    reg.register(PitUniverseEntry("U1", "00700", "2024-01-01",
                                  effective_to="2024-06-30"))
    reg.register(PitUniverseEntry("U2", "00371", "2024-07-01"))
    assert reg.stocks_known_at("2024-03-31") == ["00700", "01951"]
    assert reg.stocks_known_at("2024-08-01") == ["00371"]


def test_snapshot_hash():
    e1 = PitUniverseEntry("U1", "01951", "2024-01-01")
    assert snapshot_hash([e1]) == snapshot_hash([e1])
    assert len(snapshot_hash([e1])) == 16


def test_pit_integrity_score():
    assert pit_integrity_score("A")["integrity_score"] == 100.0
    assert pit_integrity_score("B")["research_valid"] is True
    c = pit_integrity_score("C")
    assert c["research_valid"] is False
    assert c["integrity_score"] is None
