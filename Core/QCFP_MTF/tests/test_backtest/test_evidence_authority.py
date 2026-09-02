# coding: utf-8
"""Evidence Builder 去决策权测试（新 1 号）"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.backtest.data_pipeline import \
    assert_evidence_no_decision_authority, build_evidence_timeline, \
    build_signal_timeline
from QCFP_MTF.config.settings import DEFAULT_SETTINGS


def _frames():
    structural = pd.DataFrame({
        "stock_code": ["00700"],
        "period_end": ["2026-03-31"],
        "available_date": ["2026-05-15"],
        "structural_regime": ["STRUCTURAL_DECLINE"],
        "c_state": ["C→"], "f_state": ["F→"], "p_state": ["P→"],
        "q_trend_score": [40.0], "q_position_52w": [0.03],
        "data_quality": ["A"],
    })
    monthly = pd.DataFrame({
        "stock_code": ["00700"],
        "month_end": ["2026-04-30"],
        "monthly_behavior_state": ["Improving"],
        "cbi_score": [55.0], "cbi_state": ["CBI_STABLE"],
        "cost_position": ["COST_NEUTRAL"], "data_quality": ["A"],
    })
    weekly = pd.DataFrame({
        "stock_code": ["00700"], "stock_name": ["腾讯控股"],
        "week_end": ["2026-05-29"],
        "tactical_signal": ["Breakout"],
        "data_quality": ["A"],
    })
    chip = pd.DataFrame({
        "stock_code": ["00700"], "quarter_end_date": ["2026-03-31"],
        "chip_structure_score": [60.0],
    })
    idx = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=200, freq="D"),
        "HSI": [20000.0 + i for i in range(200)],
        "VHSI": [20.0] * 200,
    })
    weekly_kl = pd.DataFrame({
        "stock_code": ["00700"], "date": pd.to_datetime(["2026-05-29"]),
        "high": [10.6], "low": [10.2], "close": [10.5],
    })
    return structural, monthly, weekly, chip, idx, weekly_kl


def test_signal_timeline_marked_shadow_only():
    structural, monthly, weekly, chip, idx, _ = _frames()
    sig = build_signal_timeline(structural, monthly, weekly, chip, idx,
                                DEFAULT_SETTINGS)
    assert sig["authority"].iloc[0] == "SHADOW_ONLY"
    assert bool(sig["non_certifiable"].iloc[0]) is True
    assert sig["legacy_action"].iloc[0] == sig["action_signal"].iloc[0]
    r = assert_evidence_no_decision_authority(sig)
    assert r["verdict"] == "SHADOW_COMPARATOR"


def test_evidence_timeline_has_no_decision_authority():
    structural, monthly, weekly, chip, idx, _ = _frames()
    ev = build_evidence_timeline(structural, monthly, weekly, chip, idx,
                                 DEFAULT_SETTINGS)
    assert "target" not in ev.columns
    assert "action_signal" not in ev.columns
    assert "legacy_target" not in ev.columns
    assert ev["evidence_authority"].iloc[0] == "EVIDENCE_ONLY"
    assert assert_evidence_no_decision_authority(
        ev)["verdict"] == "EVIDENCE_ONLY"


def test_assert_rejects_unmarked_decision_cols():
    df = pd.DataFrame({"target": [0.2], "authority": ["PRODUCTION"]})
    try:
        assert_evidence_no_decision_authority(df)
        raise AssertionError("should raise ValueError")
    except ValueError:
        pass
