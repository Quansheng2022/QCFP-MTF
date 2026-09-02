# coding: utf-8
"""Permission Opportunity Cost 测试（28 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.evaluation.permission_value import permission_value


def test_permission_justified():
    b = {"avoided_loss": 0.08, "avoided_drawdown": 0.05,
         "prevented_false_entry": 0.02, "tail_risk_reduction": 0.02}
    c = {"missed_return": 0.04, "missed_wave": 0.01,
         "entry_delay": 0.005, "capture_loss": 0.005}
    r = permission_value(b, c)
    assert r["net_permission_value"] > 0
    assert r["verdict"] == "JUSTIFIED"


def test_permission_review():
    b = {"avoided_loss": 0.01, "avoided_drawdown": 0.0,
         "prevented_false_entry": 0.0, "tail_risk_reduction": 0.0}
    c = {"missed_return": 0.10, "missed_wave": 0.05,
         "entry_delay": 0.01, "capture_loss": 0.01}
    r = permission_value(b, c)
    assert r["net_permission_value"] < 0
    assert r["verdict"] == "REVIEW"
