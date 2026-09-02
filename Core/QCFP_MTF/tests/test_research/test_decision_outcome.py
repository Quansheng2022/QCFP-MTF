# coding: utf-8
"""Decision Outcome Simulation 测试（P0-3）"""

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.research.decision_outcome import (
    OUTCOME_HORIZONS, compute_decision_outcome,
    outcome_evidence_summary, simulate_decision_outcome)


def _rows():
    return [
        {"trade_date": "2026-08-24", "close": 10.0, "high": 10.5,
         "low": 9.8},
        {"trade_date": "2026-08-25", "close": 10.4, "high": 10.8,
         "low": 10.2},
        {"trade_date": "2026-08-26", "close": 10.2, "high": 10.6,
         "low": 10.0},
        {"trade_date": "2026-08-27", "close": 11.0, "high": 11.2,
         "low": 10.1},
        {"trade_date": "2026-08-28", "close": 11.4, "high": 11.6,
         "low": 10.9},
    ]


def test_compute_decision_outcome_metrics():
    r = compute_decision_outcome(_rows(), "5D", outcome_type="TRADE")
    assert r["future_return"] > 0
    assert r["mfe"] >= r["future_return"]
    assert r["mae"] < 0
    assert r["wave_capture"] is not None
    assert r["holding_period"] == 5
    # 未成熟：只有 3 行却要 20D → None
    assert compute_decision_outcome(_rows()[:3], "20D") is None


def test_simulate_decision_outcome_maturity():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE hk_hist_daily_kline (date TEXT, stock_code TEXT, "
        "close REAL, high REAL, low REAL)")
    for i, r in enumerate(_rows()):
        conn.execute(
            "INSERT INTO hk_hist_daily_kline VALUES (?,?,?,?,?)",
            (r["trade_date"], "00700", r["close"], r["high"], r["low"]))
    dec = {"decision_id": "d1", "stock_code": "00700",
           "decision_date": "2026-08-21", "final_target": 0.2}
    s = simulate_decision_outcome(conn, dec, today="2026-08-29")
    assert s["outcome_type"] == "TRADE"
    assert s["horizons"]["5D"]["matured"] is True
    assert s["horizons"]["20D"]["matured"] is False
    assert s["auto_param_modify_forbidden"] is True
    conn.close()


def test_outcome_evidence_summary():
    sims = [
        {"horizons": {"5D": {"matured": True},
                      "20D": {"matured": False},
                      "60D": {"matured": False}}},
        {"horizons": {"5D": {"matured": True},
                      "20D": {"matured": True},
                      "60D": {"matured": False}}},
    ]
    s = outcome_evidence_summary(sims)
    assert s["outcome_maturity_5d"] == 2
    assert s["outcome_maturity_20d"] == 1
    assert s["outcome_maturity_60d"] == 0
    assert s["outcome_coverage"] == 1.0
    assert OUTCOME_HORIZONS == ("5D", "20D", "60D")
