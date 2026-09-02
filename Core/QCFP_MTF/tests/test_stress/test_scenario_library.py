# coding: utf-8
"""Standard Stress Scenario Library 测试（19 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.stress.scenario_library import (SCENARIO_LIBRARY,
                                              SCENARIO_LIBRARY_VERSION,
                                              certification_scenario_set,
                                              scenario_library)


def test_scenario_library_fixed():
    lib = scenario_library()
    assert lib["version"] == "SCEN-LIB-1.0"
    assert len(lib["scenarios"]) == 12
    for name in ("BASE", "COST_2X", "SLIPPAGE_2X", "ADV_50%",
                 "GAP_DOWN", "BEAR_REGIME", "HIGH_VOL",
                 "LIQUIDITY_SHOCK"):
        assert name in lib["scenarios"]


def test_certification_scenario_set_fixed():
    s1 = certification_scenario_set()
    s2 = certification_scenario_set()
    assert s1 == s2
    assert len(s1) == 12


def test_scenario_library_version():
    assert SCENARIO_LIBRARY_VERSION == "SCEN-LIB-1.0"
    assert "BASE" in SCENARIO_LIBRARY
