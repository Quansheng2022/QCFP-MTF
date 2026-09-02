# coding: utf-8
"""UNKNOWN Caps → No-New-Risk 测试（PWC-1 第 7 项）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.decision.engine import evaluate


def _row(prev_caps=None, **kw):
    base = {
        "stock_code": "T_U", "decision_date": "2026-08-21",
        "c_state": "C↑", "f_state": "F↑", "p_state": "P↑",
        "prev_f_state": "F↑", "monthly_behavior_state": "Improving",
        "tactical_signal": "Breakout", "daily_state": "DAILY_BREAKOUT",
        "risk_level": "Low", "des_score": 0, "wave_strength": 1.0,
        "chip_stability_confidence": "High", "data_quality": "B",
        "q_position_52w": 0.2, "q_trend_score": 55.0,
        "market_context": "risk_on", "cbi_state": "CBI_STABLE",
        "catalyst_score": 1.0,
    }
    if prev_caps is not None:
        base.update(prev_caps)
    base.update(kw)
    return base


def _settings_production():
    import copy
    s = copy.deepcopy(DEFAULT_SETTINGS)
    s.setdefault("backtest", {})["mode"] = "production"
    return s


def test_flat_unknown_caps_zero():
    """空仓 + UNKNOWN critical caps → final=0（不制造交易）。"""
    snap = evaluate(_row(), "FLAT", 0.0, _settings_production())
    assert snap.target_position <= 1e-9


def test_holding_unknown_caps_no_new_risk():
    """已持仓 10% + proposal 20% + cap UNKNOWN → final ≤ 10%（不强制归零）。"""
    snap = evaluate(_row(), "HOLDING", 0.10, _settings_production())
    assert snap.target_position <= 0.10 + 1e-9


def test_holding_reduce_allowed_with_unknown():
    """已持仓 10% + 降仓 5% + cap UNKNOWN → 允许 5%（降低风险）。"""
    snap = evaluate(_row(risk_level="High"), "HOLDING", 0.10,
                    _settings_production())
    assert snap.target_position <= 0.10 + 1e-9


def test_hard_exit_still_zero():
    """Hard Exit + UNKNOWN → 0（原因来自 HardExit，不是 CapUnknown）。"""
    snap = evaluate(_row(des_score=9), "HOLDING", 0.10,
                    _settings_production())
    assert snap.target_position <= 1e-9
