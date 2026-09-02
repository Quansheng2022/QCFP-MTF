# coding: utf-8
"""Decision Quality Monitoring 测试（47 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.monitoring.decision_quality import decision_quality_report


def _trades():
    return [
        {"net_return": 0.12, "mfe": 0.20, "mae": -0.04,
         "mfe_capture": 0.6, "permission": "ALLOW",
         "entry_timing": "OPTIMAL", "exit_timing": "normal"},
        {"net_return": -0.03, "mfe": 0.08, "mae": -0.06,
         "mfe_capture": 0.3, "permission": "ALLOW",
         "entry_timing": "LATE", "exit_timing": "early"},
        {"net_return": 0.05, "mfe": 0.10, "mae": -0.03,
         "mfe_capture": 0.5, "permission": "TEST",
         "entry_timing": "EARLY", "exit_timing": "normal"},
    ]


def test_decision_quality_report():
    r = decision_quality_report(_trades())
    assert r["n"] == 3
    assert abs(r["wave_quality"]["hit_rate"] - 2 / 3) < 1e-4
    assert r["permission_quality"]["allow_win_rate"] == 0.5
    assert r["entry_quality"]["OPTIMAL"] == 1
    assert r["exit_quality"]["early"] == 1
    assert r["fsm_quality"]["abnormal_rate"] == 0.0


def test_decision_quality_empty():
    assert decision_quality_report([])["n"] == 0
