# coding: utf-8
"""Wave → Canonical Engine 接线测试（新 5 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.decision.engine import evaluate


def _row(wave_stage, **kw):
    base = {
        "stock_code": "T_WAVE", "decision_date": "2026-08-21",
        "c_state": "C↑", "f_state": "F↑", "p_state": "P↑",
        "prev_f_state": "F↑", "monthly_behavior_state": "Improving",
        "tactical_signal": "Breakout", "daily_state": "DAILY_BREAKOUT",
        "risk_level": "Low", "des_score": 0, "wave_strength": 0.8,
        "chip_stability_confidence": "High", "data_quality": "B",
        "q_position_52w": 0.2, "q_trend_score": 55.0,
        "market_context": "risk_on", "cbi_state": "CBI_STABLE",
        "catalyst_score": 1.0, "wave_stage": wave_stage,
        "wave_id": "W-001",
    }
    base.update(kw)
    return base


def test_wave_discovery_blocks_entry():
    """DISCOVERY 阶段 + 空仓：Wave 门拒绝新增风险 → target=0。"""
    snap = evaluate(_row("DISCOVERY"), "FLAT", 0.0, DEFAULT_SETTINGS)
    assert snap.wave_stage == "DISCOVERY"
    assert snap.wave_action_allowed is False
    assert snap.wave_proposal_target == 0.0
    assert snap.target_position <= 1e-9


def test_wave_active_allows_proposal():
    snap = evaluate(_row("ACTIVE"), "FLAT", 0.0, DEFAULT_SETTINGS)
    assert snap.wave_stage == "ACTIVE"
    assert snap.wave_action_allowed is True
    assert snap.wave_entry_scale == 1.0
    assert snap.wave_proposal_target <= 0.5 + 1e-9  # permission max_target
    assert snap.wave_id == "W-001"


def test_wave_confirming_scales_entry():
    snap = evaluate(_row("CONFIRMING"), "FLAT", 0.0, DEFAULT_SETTINGS)
    assert snap.wave_stage == "CONFIRMING"
    assert snap.wave_entry_scale == 0.5
    if snap.wave_action_allowed:
        assert snap.wave_proposal_target <= 0.5 + 1e-9


def test_wave_fields_absent_default():
    row = _row("ACTIVE")
    del row["wave_stage"]
    del row["wave_id"]
    snap = evaluate(row, "FLAT", 0.0, DEFAULT_SETTINGS)
    assert snap.wave_stage == ""
    assert snap.wave_action_allowed is False
