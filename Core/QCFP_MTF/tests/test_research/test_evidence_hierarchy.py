# coding: utf-8
"""Evidence Hierarchy 测试（93 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.research.evidence_hierarchy import EVIDENCE_LEVELS, \
    evidence_level_check


def test_production_requires_ablation_stress():
    r = evidence_level_check("NewAlpha", 3, target="PRODUCTION")
    assert r["ok"] is False
    assert r["verdict"] == "INSUFFICIENT"
    r2 = evidence_level_check("NewAlpha", 4, target="PRODUCTION")
    assert r2["ok"] is True
    assert r2["level_name"] == "ABLATION_STRESS"


def test_theory_only_hypothesis():
    r = evidence_level_check("Idea", 0, target="HYPOTHESIS")
    assert r["ok"] is True
    r2 = evidence_level_check("Idea", 0, target="PRODUCTION")
    assert r2["ok"] is False
    assert r2["verdict"] == "INSUFFICIENT"


def test_levels_defined():
    assert EVIDENCE_LEVELS[6] == "PRODUCTION"
    assert EVIDENCE_LEVELS[3] == "OOS_WALK_FORWARD"
