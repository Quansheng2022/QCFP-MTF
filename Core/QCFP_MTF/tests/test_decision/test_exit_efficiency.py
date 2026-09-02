# coding: utf-8
"""Exit Efficiency / EXIT Taxonomy 测试（75 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.exit_quality import exit_efficiency, exit_taxonomy


def test_exit_efficiency():
    r = exit_efficiency(0.14, 0.20)
    assert r["efficiency"] == 0.7
    assert r["grade"] == "GOOD"
    assert exit_efficiency(0.18, 0.20)["grade"] == "EXCELLENT"
    assert exit_efficiency(0.09, 0.20)["grade"] == "FAIR"
    assert exit_efficiency(0.0, 0.20)["grade"] == "POOR"


def test_exit_efficiency_no_mfe():
    r = exit_efficiency(0.05, 0.0)
    assert r["efficiency"] is None


def test_exit_taxonomy_mapping():
    assert exit_taxonomy("HARD") == "EXIT_HARD"
    assert exit_taxonomy("WAVE") == "EXIT_DECAY"
    assert exit_taxonomy("TIME") == "EXIT_TIME"
    assert exit_taxonomy("REGIME") == "EXIT_REGIME"
    assert exit_taxonomy("PROFIT") == "EXIT_TRAILING"
    assert exit_taxonomy("NONE") == ""
