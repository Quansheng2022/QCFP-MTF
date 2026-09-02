# coding: utf-8
"""Production Architecture 2.0 测试（30 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.three_worlds import (WORLDS, promote_to_production,
                                              shadow_comparison,
                                              three_worlds_gate)


def test_research_world():
    assert three_worlds_gate("RESEARCH", "EXPERIMENT").allowed is True
    assert three_worlds_gate("RESEARCH",
                             "PRODUCTION_DECISION").allowed is False


def test_shadow_world():
    assert three_worlds_gate("SHADOW", "PARALLEL_RUN").allowed is True
    assert three_worlds_gate("SHADOW",
                             "PRODUCTION_DECISION").allowed is False


def test_production_world():
    assert three_worlds_gate("PRODUCTION",
                             "CERTIFIED_DECISION").allowed is True
    assert three_worlds_gate("PRODUCTION",
                             "EXPERIMENT").allowed is False


def test_promote_to_production():
    ok, missing = promote_to_production({"pit": True, "oos": True,
                                         "ablation": True, "stress": True,
                                         "replay": True,
                                         "certification": True,
                                         "shadow": True})
    assert ok and not missing
    ok, missing = promote_to_production({"pit": True, "oos": True})
    assert not ok and "ablation" in missing


def test_shadow_comparison():
    r = shadow_comparison(
        {"decision": 0.5, "position": 0.05, "outcome": 0.1},
        {"decision": 0.52, "position": 0.06, "outcome": 0.11})
    assert r["max_difference"] > 0
    assert r["acceptable"] is True


def test_worlds_constant():
    assert WORLDS == ("RESEARCH", "SHADOW", "PRODUCTION")
