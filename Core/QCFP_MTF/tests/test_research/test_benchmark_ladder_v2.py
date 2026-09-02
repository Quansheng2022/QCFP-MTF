# coding: utf-8
"""Benchmark Ladder B0–B6 测试（新 28 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.research.benchmark_ladder import BENCHMARK_BASELINES, \
    benchmark_ladder_baselines, core_vs_full


def test_baselines_defined():
    keys = [k for k, _ in BENCHMARK_BASELINES]
    assert keys == ["B0_CASH", "B1_BUY_HOLD", "B2_SIMPLE_TREND",
                    "B3_WAVE_ONLY", "B4_PERMISSION_WAVE",
                    "B5_PERMISSION_WAVE_FSM_RISK", "B6_FULL_CANONICAL"]


def test_baseline_rows():
    r = benchmark_ladder_baselines({
        "B0_CASH": {"sharpe": 0.0},
        "B6_FULL_CANONICAL": {"sharpe": 1.3}})
    assert r["baselines"]["B0_CASH"]["label"] == "Cash"
    assert r["baselines"]["B6_FULL_CANONICAL"]["metrics"]["sharpe"] == 1.3


def test_core_preferred_when_no_increment():
    r = core_vs_full({"sharpe": 1.29}, {"sharpe": 1.31},
                     core_modules=9, full_modules=25)
    assert r["verdict"] == "CORE_PREFERRED"
    assert r["full_complexity_double"] is True


def test_full_justified_with_increment():
    r = core_vs_full({"sharpe": 1.0}, {"sharpe": 1.4},
                     core_modules=9, full_modules=25)
    assert r["verdict"] == "FULL_JUSTIFIED"
