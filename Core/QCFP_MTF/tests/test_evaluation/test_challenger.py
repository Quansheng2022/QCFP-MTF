# coding: utf-8
"""Benchmark / Challenger System 测试（29 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.evaluation.challenger import challenger_system


def _models():
    return {
        "Buy&Hold": {"cagr": 0.12, "mdd": -0.35, "sharpe": 0.55},
        "Wave-only": {"cagr": 0.18, "mdd": -0.29, "sharpe": 0.72},
        "Permission-only": {"cagr": 0.14, "mdd": -0.18, "sharpe": 0.76},
        "QCFP_MTF": {"cagr": 0.21, "mdd": -0.16, "sharpe": 1.31},
        "Challenger": {"cagr": 0.20, "mdd": -0.17, "sharpe": 1.22},
    }


def test_challenger_beats():
    r = challenger_system(_models())
    assert r["qcfp_rank"] == 1
    assert r["verdict"] == "BEATS_CHALLENGERS"
    assert r["sharpe_edge"] > 0
    assert r["mdd_advantage"] > 0


def test_challenger_requires_qcfp():
    r = challenger_system({"A": {"cagr": 0.1, "mdd": -0.2, "sharpe": 0.9}})
    assert "error" in r
