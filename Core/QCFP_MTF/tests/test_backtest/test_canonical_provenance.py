# coding: utf-8
"""Canonical Provenance 测试（P0-1 号）"""

import sys
import warnings
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

import pandas as pd

from QCFP_MTF.backtest.engine import run_backtest


def _weekly():
    return pd.DataFrame({
        "stock_code": ["01951", "01951"],
        "date": ["2026-01-01", "2026-01-08"],
        "close": [10.0, 10.5]})


def _signals(provenance=False):
    s = pd.DataFrame({
        "stock_code": ["01951", "01951"],
        "decision_date": ["2026-01-01", "2026-01-08"],
        "action_signal": ["BUY", "HOLD"],
        "target": [0.05, 0.05],
        "mtf_regime": ["BULLISH", "BULLISH"],
        "market_regime": ["Bull", "Bull"],
        "structural_regime": ["STRUCTURAL_ACCUMULATION",
                              "STRUCTURAL_ACCUMULATION"]})
    if provenance:
        s["canonical_target"] = [0.04, 0.04]
        s["canonical_provenance"] = "canonical_replay"
    return s


def test_formal_mode_rejects_non_canonical():
    settings = {"backtest": {"mode": "production"}}
    try:
        run_backtest(_signals(), _weekly(), settings)
        raise AssertionError("should raise")
    except ValueError as exc:
        assert "Canonical-only" in str(exc)


def test_research_mode_warns_but_runs():
    settings = {"backtest": {"mode": "research_exploration"}}
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        run_backtest(_signals(), _weekly(), settings)
        assert any("Canonical-only" in str(x.message) for x in w)


def test_canonical_target_used():
    settings = {"backtest": {"mode": "production"}}
    result = run_backtest(_signals(provenance=True), _weekly(), settings)
    assert "position" in result.columns
    assert "weekly_return" in result.columns
