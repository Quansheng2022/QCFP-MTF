# coding: utf-8
"""Minimum Governed Core 决策测试（新 30 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.minimal_governed_core import \
    minimum_governed_core_decision


def test_simplify_when_double_complexity_low_value():
    full = {"sharpe": 1.31, "mdd": -0.10, "wave_capture": 0.72,
            "practicality": 0.80}
    minimal = {"sharpe": 1.29, "mdd": -0.11, "wave_capture": 0.70,
               "practicality": 0.85}
    r = minimum_governed_core_decision(full, minimal,
                                       full_complexity=2.0,
                                       minimal_complexity=1.0)
    assert r["complexity_ratio"] == 2.0
    assert r["value_gain"] < 0.05
    assert r["verdict"] == "SIMPLIFY"


def test_keep_full_with_real_increment():
    full = {"sharpe": 1.8, "mdd": -0.05, "wave_capture": 0.9,
            "practicality": 0.9}
    minimal = {"sharpe": 1.0, "mdd": -0.2, "wave_capture": 0.5,
               "practicality": 0.6}
    r = minimum_governed_core_decision(full, minimal)
    assert r["value_gain"] >= 0.05
    assert r["verdict"] == "KEEP_FULL"


def test_default_simplify_when_equal():
    m = {"sharpe": 1.3, "mdd": -0.10, "wave_capture": 0.7,
         "practicality": 0.8}
    r = minimum_governed_core_decision(m, m)
    assert r["verdict"] == "SIMPLIFY"
