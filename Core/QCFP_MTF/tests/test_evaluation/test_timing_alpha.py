# coding: utf-8
"""Entry/Exit Alpha + Timing Alpha 测试（P1-9 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.evaluation.timing_alpha import entry_alpha, exit_alpha, \
    timing_alpha


def test_entry_alpha():
    assert entry_alpha(10.0, 9.5)["entry_alpha"] > 0       # 实际更贵
    assert entry_alpha(9.51, 9.5)["grade"] == "OPTIMAL"
    assert entry_alpha(10.5, 9.5)["grade"] == "VERY_LATE"


def test_exit_alpha():
    r = exit_alpha(11.5, 12.0)
    assert r["exit_alpha"] > 0
    assert abs(r["capture"] - 11.5 / 12.0) < 1e-4
    assert exit_alpha(11.8, 12.0)["grade"] == "EXCELLENT"


def test_timing_alpha():
    r = timing_alpha(0.03, 0.05)
    assert r["timing_alpha"] == 0.08
    assert r["quality"] == "GOOD"
    assert timing_alpha(0.0, 0.0)["quality"] == "EXCELLENT"
