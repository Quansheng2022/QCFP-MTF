# coding: utf-8
"""False Positive / False Negative Lab 测试（28 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.evaluation.fpfn_lab import fpfn_analysis


def _decisions():
    return [
        {"predicted_buy": True, "actual_win": True, "net_return": 0.10},
        {"predicted_buy": True, "actual_win": False, "net_return": -0.08,
         "false_positive_reason": "WAVE_FALSE_POSITIVE"},
        {"predicted_buy": True, "actual_win": False, "net_return": -0.05,
         "false_positive_reason": "ENTRY_LATE"},
        {"predicted_buy": False, "actual_win": True, "net_return": 0.20,
         "miss_reason": "PERMISSION_BLOCK"},
        {"predicted_buy": False, "actual_win": False, "net_return": -0.02},
    ]


def test_fpfn_quadrant():
    r = fpfn_analysis(_decisions())
    assert r["quadrant"] == {"TP": 1, "FP": 2, "FN": 1, "TN": 1}
    assert r["fp_reasons"]["WAVE_FALSE_POSITIVE"] == 1
    assert r["fn_reasons"]["PERMISSION_BLOCK"] == 1
    assert r["conclusion"] == "FN_DOMINANT"     # FN cost 0.20 > FP 0.13


def test_fpfn_metrics():
    r = fpfn_analysis(_decisions())
    assert abs(r["precision"] - 1 / 3) < 1e-4
    assert abs(r["recall"] - 0.5) < 1e-4
    assert 0 < r["f1"] < 1
