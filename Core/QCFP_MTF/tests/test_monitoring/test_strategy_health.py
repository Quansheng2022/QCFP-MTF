# coding: utf-8
"""Strategy Health Score 测试（49 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.monitoring.strategy_health import (DIMENSIONS,
                                                 evaluate_strategy_health,
                                                 health_from_metrics,
                                                 health_to_md)


def test_healthy_all_scores():
    h = evaluate_strategy_health({d: 85 for d in DIMENSIONS})
    assert h.overall_band == "HEALTHY"
    assert not h.critical and not h.degraded


def test_degraded_by_one_dimension():
    scores = {d: 85 for d in DIMENSIONS}
    scores["wave"] = 55
    h = evaluate_strategy_health(scores)
    assert h.overall_band == "DEGRADED"
    assert "wave" in h.degraded


def test_critical_dominates():
    scores = {d: 80 for d in DIMENSIONS}
    scores["ledger"] = 20
    h = evaluate_strategy_health(scores)
    assert h.overall_band == "CRITICAL"
    assert "ledger" in h.critical


def test_health_from_metrics():
    h = health_from_metrics({
        "data_missing_rate": 0.02, "pit_grade": "B",
        "permission_flip_rate": 0.05, "wave_capture_trend": 0.9,
        "slippage_ratio": 1.5, "risk_budget_breach": 0.0,
        "settings_drift": 0.0, "ledger_integrity": True,
        "replay_consistent": True, "research_validated": False})
    assert h.overall_band in ("HEALTHY", "DEGRADED")


def test_health_to_md():
    md = health_to_md(evaluate_strategy_health({d: 80 for d in DIMENSIONS}))
    assert "Strategy Health" in md
    assert "HEALTHY" in md
