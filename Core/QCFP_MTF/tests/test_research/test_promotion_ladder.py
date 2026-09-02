# coding: utf-8
"""Benchmark Ladder Promotion 门测试（新 52 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.research.benchmark_ladder import benchmark_ladder_baselines, \
    promotion_requires_ladder


def _ladder():
    return benchmark_ladder_baselines({
        "B3_WAVE_ONLY": {"sharpe": 0.6},
        "B4_PERMISSION_WAVE": {"sharpe": 0.8},
        "B6_FULL_CANONICAL": {"sharpe": 1.0}})


def test_ladder_present_allows_promotion():
    r = promotion_requires_ladder(_ladder())
    assert r["verdict"] == "LADDER_PRESENT"
    assert r["allowed"] is True


def test_missing_baseline_blocks():
    r = promotion_requires_ladder(benchmark_ladder_baselines({}))
    assert r["verdict"] == "PROMOTION_BLOCKED"
    assert r["allowed"] is False
    assert "B4_PERMISSION_WAVE" in r["missing_baselines"]


def test_missing_full_blocks():
    ladder = benchmark_ladder_baselines({
        "B3_WAVE_ONLY": {"sharpe": 0.6}})
    r = promotion_requires_ladder(ladder)
    assert r["allowed"] is False
