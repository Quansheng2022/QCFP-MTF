# coding: utf-8
"""Decision Robustness Score 测试（91 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.decision.stability import decision_robustness, stability_report


def _row():
    return {"stock_code": "T_ROB", "decision_date": "2026-08-21",
            "c_state": "C↑", "f_state": "F↑", "p_state": "P↑",
            "prev_f_state": "F↑", "monthly_behavior_state": "Improving",
            "tactical_signal": "Breakout", "daily_state": "DAILY_BREAKOUT",
            "risk_level": "Medium", "des_score": 1,
            "chip_stability_confidence": "High", "data_quality": "B",
            "q_position_52w": 0.3, "wave_strength": 0.8}


def test_decision_robustness_runs():
    r = decision_robustness(_row(), DEFAULT_SETTINGS, n_perturbations=18)
    assert r["band"] in ("ROBUST", "FRAGILE", "UNSTABLE")
    assert 0 <= r["robustness_score"] <= 100
    assert "flips_by_dimension" in r


def test_stability_report_compat():
    r = stability_report(_row(), DEFAULT_SETTINGS, n_perturbations=10)
    assert "stability_score" in r
