# coding: utf-8
"""Canonical-only OOS/Ablation/Stress 测试（新 8 号）"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.backtest.canonical_runs import run_canonical_ablation, \
    run_canonical_backtest, run_canonical_oos, run_canonical_stress, \
    run_legacy_shadow_comparator
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
        "stock_code": ["00700", "00700"], "stock_name": ["腾讯控股"] * 2,
        "week_end": ["2026-05-29", "2026-06-05"],
        "tactical_signal": ["Breakout", "Breakout"],
        "data_quality": ["A", "A"],
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
        "stock_code": ["00700", "00700", "00700"],
        "date": pd.to_datetime(["2026-05-22", "2026-05-29", "2026-06-05"]),
        "high": [10.0, 10.6, 11.0], "low": [9.8, 10.2, 10.7],
        "close": [10.0, 10.5, 10.9],
    })
    return structural, monthly, weekly, chip, idx, weekly_kl


def test_canonical_backtest_provenance():
    structural, monthly, weekly, chip, idx, weekly_kl = _frames()
    r = run_canonical_backtest(structural, monthly, weekly, chip, idx,
                               DEFAULT_SETTINGS, weekly_kl=weekly_kl,
                               run_id="T_BT")
    assert r["provenance"]["engine"] == "canonical"
    assert r["provenance"]["feature_manifest_hash"]
    assert r["provenance"]["strategy_version"]
    assert not r["backtest"].empty


def test_canonical_oos_split():
    structural, monthly, weekly, chip, idx, weekly_kl = _frames()
    r = run_canonical_oos(structural, monthly, weekly, chip, idx,
                          DEFAULT_SETTINGS, train_end="2026-05-29",
                          test_start="2026-06-05", test_end="2026-06-05",
                          weekly_kl=weekly_kl, run_id="T_OOS")
    assert r["provenance"]["engine"] == "canonical"
    assert not r["oos_backtest"].empty


def test_canonical_ablation_and_stress():
    structural, monthly, weekly, chip, idx, weekly_kl = _frames()
    a = run_canonical_ablation(
        structural, monthly, weekly, chip, idx, DEFAULT_SETTINGS,
        ablations=[{"label": "FULL", "settings": DEFAULT_SETTINGS}],
        weekly_kl=weekly_kl, run_id="T_ABL")
    assert a["provenance"]["engine"] == "canonical"
    assert "FULL" in a["variants"]
    s = run_canonical_stress(
        structural, monthly, weekly, chip, idx, DEFAULT_SETTINGS,
        stress_settings=[{"label": "BASE",
                          "settings": DEFAULT_SETTINGS}],
        weekly_kl=weekly_kl, run_id="T_STRESS")
    assert s["provenance"]["engine"] == "canonical"
    assert "BASE" in s["scenarios"]


def test_legacy_comparator_shadow_only():
    structural, monthly, weekly, chip, idx, weekly_kl = _frames()
    r = run_legacy_shadow_comparator(structural, monthly, weekly, chip,
                                     idx, DEFAULT_SETTINGS,
                                     weekly_kl=weekly_kl,
                                     run_id="T_LEGACY")
    assert r["authority"] == "SHADOW_ONLY"
    assert r["non_certifiable"] is True
    assert r["provenance"]["engine"] == "legacy_comparator"
    assert r["provenance"]["certifiable"] is False
