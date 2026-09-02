# coding: utf-8
"""Model Doubt Index 测试（P1-10 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.doubt_index import doubt_adjusted_budget, \
    model_doubt_index


def test_normal():
    d = model_doubt_index({})
    assert d.band == "NORMAL"
    assert d.risk_budget_scale == 1.0


def test_caution():
    d = model_doubt_index({"mfe_decline": 1.0, "wave_hit_decline": 0.9})
    assert d.score >= 20
    assert d.band == "CAUTION"


def test_halted_high_doubt():
    d = model_doubt_index({"data_drift": 1.0, "feature_drift": 1.0,
                           "pit_degradation": 1.0, "permission_drift": 1.0,
                           "wave_hit_decline": 1.0, "mfe_decline": 1.0,
                           "mae_increase": 1.0, "calibration_error": 1.0,
                           "oos_decay": 1.0, "slippage_increase": 1.0,
                           "decision_flip": 1.0})
    assert d.band == "HALTED"
    assert d.risk_budget_scale == 0.0


def test_doubt_adjusted_budget():
    d = model_doubt_index({"pit_degradation": 1.0, "oos_decay": 0.8,
                           "data_drift": 0.9})
    r = doubt_adjusted_budget(d, 0.10)
    assert r["adjusted_budget"] < 0.10
