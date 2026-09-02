# coding: utf-8
"""Benchmark Ladder B2–B6 OOS 表测试（Release 3：新 28 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.research.benchmark_ladder import benchmark_missing_gate, \
    oos_benchmark_table


def _metrics():
    return {m: {"sharpe": 0.5} for m in (
        "B2_SIMPLE_TREND", "B3_WAVE_ONLY", "B4_PERMISSION_WAVE",
        "B5_PERMISSION_WAVE_FSM_RISK", "B6_FULL_CANONICAL")}


def test_complete_table():
    t = oos_benchmark_table(_metrics())
    assert t["complete"] is True
    assert t["missing"] == []


def test_missing_blocks_promotion():
    t = oos_benchmark_table({"B6_FULL_CANONICAL": {"sharpe": 1.0}})
    r = benchmark_missing_gate(t)
    assert r["verdict"] == "PROMOTION_BLOCKED"
    assert r["allowed"] is False
    assert "B2_SIMPLE_TREND" in r["missing_models"]
