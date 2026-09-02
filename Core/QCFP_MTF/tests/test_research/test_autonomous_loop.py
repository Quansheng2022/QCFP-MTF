# coding: utf-8
"""Autonomous Research Loop 测试（50 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.research.autonomous_loop import (AutonomousResearchController,
                                               LOOP_STAGES,
                                               autonomous_research_loop)


def test_loop_advance():
    r = autonomous_research_loop("DISCOVER")
    assert r["stage"] == "HYPOTHESIS"
    assert r["blocked"] is False


def test_certification_gate():
    r = autonomous_research_loop("CERTIFICATION", checks={"certified": False})
    assert r["blocked"] is True
    r2 = autonomous_research_loop("CERTIFICATION", checks={"certified": True})
    assert r2["blocked"] is False
    assert r2["stage"] == "SHADOW"


def test_full_loop_controller():
    c = AutonomousResearchController()
    for _ in range(20):
        checks = {"certified": True, "shadow_ok": True,
                  "decay_confirmed": True}
        c.advance(checks)
    assert c.current in LOOP_STAGES
    assert c.summary()["stages_visited"] > 0


def test_loop_stages_constant():
    assert LOOP_STAGES[0] == "DISCOVER"
    assert LOOP_STAGES[-1] == "RESEARCH"
