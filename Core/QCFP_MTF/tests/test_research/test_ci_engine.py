# coding: utf-8
"""CI Engine 测试（35 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.research.ci_engine import (bootstrap_ci, metric_ci,
                                         sharpe_ci, win_rate_ci)


def _returns():
    return [0.01, 0.02, -0.01, 0.03, 0.005, -0.005, 0.02, 0.01]


def test_bootstrap_ci():
    lo, hi = bootstrap_ci([0.1, 0.2, 0.3, 0.4, 0.5], n=200)
    assert lo is not None and hi is not None
    assert lo <= hi


def test_sharpe_ci():
    r = sharpe_ci(_returns(), n=200)
    assert r["sharpe"] is not None
    assert r["ci_low"] <= r["ci_high"]


def test_win_rate_ci():
    r = win_rate_ci([0.1, -0.05, 0.2, 0.3, -0.1], n=200)
    assert r["win_rate"] == 0.6
    assert r["ci_low"] <= r["ci_high"]


def test_metric_ci():
    r = metric_ci([0.1, 0.2, 0.3])
    assert r["label"] == "return"
    assert r["mean"] == 0.2
