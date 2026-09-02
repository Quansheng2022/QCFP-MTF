# coding: utf-8
"""Benchmark Ladder 测试（52 号：最小基准阶梯）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.research.benchmark_ladder import benchmark_ladder, \
    benchmark_simple_vs_full


def _ladder_metrics():
    return {
        "SIMPLE_BASELINE": {"sharpe": 0.30, "mdd": -0.20, "ret": 0.05},
        "CORE_MODEL": {"sharpe": 0.50, "mdd": -0.18, "ret": 0.09},
        "GOVERNED_MODEL": {"sharpe": 0.70, "mdd": -0.12, "ret": 0.11},
        "FULL_PRODUCTION": {"sharpe": 0.85, "mdd": -0.10, "ret": 0.13},
    }


def test_ladder_increments_proven():
    r = benchmark_ladder(_ladder_metrics())
    assert r["all_increments_proven"] is True
    assert len(r["ladder"]) == 4
    assert r["ladder"][-1]["increment"]["sharpe_delta"] > 0


def test_ladder_missing_rung():
    metrics = _ladder_metrics()
    del metrics["GOVERNED_MODEL"]
    r = benchmark_ladder(metrics)
    assert r["ladder"][2]["available"] is False
    assert r["all_increments_proven"] is False


def test_simple_vs_full_no_incremental_value():
    r = benchmark_simple_vs_full({"sharpe": 0.32, "mdd": -0.19},
                                 {"sharpe": 0.30, "mdd": -0.20})
    assert r["incremental_value"] is False
    assert r["conclusion"] == "无净增量"


def test_simple_vs_full_incremental_value():
    r = benchmark_simple_vs_full({"sharpe": 0.85, "mdd": -0.10},
                                 {"sharpe": 0.30, "mdd": -0.20})
    assert r["incremental_value"] is True
    assert r["conclusion"] == "有净增量"
