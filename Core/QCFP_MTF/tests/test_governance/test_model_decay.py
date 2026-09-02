# coding: utf-8
"""Model Decay / Retirement 测试（48 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.model_decay import (RETIREMENT_LADDER,
                                             advance_retirement_ladder,
                                             decay_to_md, model_decay_score)


def test_healthy_model():
    d = model_decay_score({})
    assert d["stage"] == "PRODUCTION"
    assert d["score"] >= 80


def test_decay_detected():
    d = model_decay_score({"oos_sharpe_trend": 0.5, "mfe_trend": 0.6,
                           "mfe_capture_trend": 0.5, "mae_trend": 1.5,
                           "calibration_trend": 0.6, "turnover_trend": 2.0,
                           "cost_sensitivity": 2.0,
                           "regime_dependence": 2.0})
    assert d["score"] < 40
    assert d["stage"] == "RETIREMENT_CANDIDATE"
    assert d["retire"] is True
    assert "OOS_SHARPE_DOWN" in d["decay_flags"]


def test_retirement_ladder():
    assert advance_retirement_ladder("PRODUCTION", "AGING") == "AGING"
    assert advance_retirement_ladder("AGING", "DEGRADED") == "DEGRADED"
    try:
        advance_retirement_ladder("DEGRADED", "PRODUCTION")
        raise AssertionError("should raise")
    except ValueError:
        pass
    assert RETIREMENT_LADDER[-1] == "RETIRED"


def test_decay_to_md():
    md = decay_to_md(model_decay_score({}))
    assert "Model Decay" in md
