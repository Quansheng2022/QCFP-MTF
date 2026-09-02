# coding: utf-8
"""WaveProposalTarget 单调不变量测试（Convergence 新 3 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.canonical_action import wave_proposal_monotonic
from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.decision.engine import evaluate


def test_monotonic_invariant():
    r = wave_proposal_monotonic(0.10, 0.05, 0.05)
    assert r["monotonic"] is True
    assert r["verdict"] == "MONOTONIC"


def test_monotonic_fail_when_final_grows_back():
    r = wave_proposal_monotonic(0.10, 0.05, 0.10)
    assert r["monotonic"] is False
    assert r["verdict"] == "WAVE_PROPOSAL_MONOTONICITY_FAIL"


def test_hard_exit_excluded():
    r = wave_proposal_monotonic(0.10, 0.05, 0.0)
    assert r["monotonic"] is True


def test_engine_wave_proposal_frozen():
    row = {
        "stock_code": "T_W", "decision_date": "2026-08-21",
        "c_state": "C↑", "f_state": "F↑", "p_state": "P↑",
        "prev_f_state": "F↑", "monthly_behavior_state": "Improving",
        "tactical_signal": "Breakout", "daily_state": "DAILY_BREAKOUT",
        "risk_level": "Low", "des_score": 0, "wave_strength": 0.8,
        "chip_stability_confidence": "High", "data_quality": "B",
        "q_position_52w": 0.2, "q_trend_score": 55.0,
        "market_context": "risk_on", "cbi_state": "CBI_STABLE",
        "catalyst_score": 1.0, "wave_stage": "CONFIRMING",
        "wave_id": "W-1", "liquidity_cap": 0.3,
    }
    snap = evaluate(row, "FLAT", 0.0, DEFAULT_SETTINGS)
    # FinalTarget ≤ WaveProposalTarget ≤ FSMProposalTarget
    assert snap.target_position <= snap.wave_proposal_target + 1e-9
    assert snap.wave_proposal_target <= snap.fsm_proposal_target + 1e-9
    assert snap.fsm_proposal_target > 0
