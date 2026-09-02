# coding: utf-8
"""Scenario Stress Engine 测试（46 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.decision.engine import evaluate
from QCFP_MTF.stress.scenario_engine import SCENARIOS, scenario_engine, \
    scenario_to_md, scenario_verdict


def _row():
    return {"stock_code": "T_SC", "decision_date": "2026-08-21",
            "c_state": "C↑", "f_state": "F↑", "p_state": "P↑",
            "prev_f_state": "F↑", "monthly_behavior_state": "Improving",
            "tactical_signal": "Breakout", "daily_state": "DAILY_BREAKOUT",
            "risk_level": "Medium", "des_score": 1,
            "chip_stability_confidence": "High", "data_quality": "B",
            "q_position_52w": 0.3}


def test_scenario_engine_runs_all():
    rep = scenario_engine(evaluate, _row(), "FLAT", 0.0, DEFAULT_SETTINGS)
    assert len(rep["scenarios"]) == len(SCENARIOS)
    for name, r in rep["scenarios"].items():
        assert "target" in r and "permission" in r


def test_scenario_verdict():
    rep = scenario_engine(evaluate, _row(), "FLAT", 0.0, DEFAULT_SETTINGS)
    verdict = scenario_verdict(rep)
    assert verdict in ("PASS_NO_EXPOSURE", "PASS_RISK_RESPONSIVE",
                       "FAIL_NOT_RISK_RESPONSIVE")


def test_scenario_to_md():
    rep = scenario_engine(evaluate, _row(), "FLAT", 0.0, DEFAULT_SETTINGS)
    md = scenario_to_md(rep)
    assert "Scenario Stress" in md
