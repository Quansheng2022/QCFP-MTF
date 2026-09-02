# coding: utf-8
"""Scenario Stress Matrix 测试（92 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.decision.engine import evaluate
from QCFP_MTF.stress.stress_matrix import MATRIX_SCENARIOS, \
    scenario_parameters, stress_matrix


def _row():
    return {"stock_code": "T_MX", "decision_date": "2026-08-21",
            "c_state": "C↑", "f_state": "F↑", "p_state": "P↑",
            "prev_f_state": "F↑", "monthly_behavior_state": "Improving",
            "tactical_signal": "Breakout", "daily_state": "DAILY_BREAKOUT",
            "risk_level": "Medium", "des_score": 1,
            "chip_stability_confidence": "High", "data_quality": "B",
            "q_position_52w": 0.3, "wave_strength": 0.8}


def test_scenario_parameters():
    p = scenario_parameters(MATRIX_SCENARIOS[4])   # Crash/Extreme/Collapse/Exit
    assert p["risk_level"] == "Extreme"
    assert p["permission"] == "BLOCK"
    assert p["portfolio_state"] == "RISK_OFF"
    assert p["liquidity_flag"] == "LIQUIDITY_LOW"


def test_stress_matrix_runs():
    m = stress_matrix(evaluate, _row(), "FLAT", 0.0, DEFAULT_SETTINGS)
    assert len(m["scenarios"]) == 5
    assert all("target" in s for s in m["scenarios"])
    assert "all_safe" in m
