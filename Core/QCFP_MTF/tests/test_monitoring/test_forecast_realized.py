# coding: utf-8
"""Forecast-to-Realized 分层校准测试（24 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.monitoring.forecast_realized import (calibration_summary,
                                                   calibration_table,
                                                   compare_trade,
                                                   stratified_calibration)


def _cmp(mfe=0.10, mae=-0.04, holding=4, layer_key="permission",
         layer="ALLOW"):
    return {
        "trade_id": "t1", "expected_mfe": 0.15, "actual_mfe": mfe,
        "mfe_error": round(mfe - 0.15, 4),
        "expected_mae": -0.05, "actual_mae": mae,
        "mae_error": round(mae + 0.05, 4),
        "expected_holding": 4, "actual_holding": holding,
        "holding_error": holding - 4,
        "actual_return": 0.08, layer_key: layer,
    }


def test_compare_trade():
    c = compare_trade({"trade_id": "t1", "mfe": 0.10, "mae": -0.04,
                       "holding_weeks": 4, "net_return": 0.08},
                      {"expected_mfe": 0.15, "expected_mae": -0.05,
                       "expected_holding": 4})
    assert c["mfe_error"] == -0.05
    assert c["holding_error"] == 0


def test_calibration_summary_detects_overestimate():
    cmps = [_cmp(mfe=0.08), _cmp(mfe=0.10)]
    s = calibration_summary(cmps)
    assert s["mfe_systematic_overestimate"] is True
    assert s["n"] == 2


def test_stratified_calibration_by_permission():
    cmps = [_cmp(layer="ALLOW"), _cmp(layer="BLOCK")]
    out = stratified_calibration(cmps, layer_key="permission")
    assert set(out) == {"ALLOW", "BLOCK"}
    assert out["ALLOW"]["n"] == 1


def test_calibration_table():
    trades = [{"trade_quality": 70, "mfe": 0.12, "mae": -0.05,
               "holding_weeks": 5}]
    t = calibration_table(trades)
    assert "60-80" in t
    assert t["60-80"]["n"] == 1
