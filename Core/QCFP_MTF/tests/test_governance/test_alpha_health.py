# coding: utf-8
"""Alpha Health Early Warning 测试（89 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.model_decay import alpha_health


def test_alpha_healthy():
    r = alpha_health({})
    assert r["band"] == "HEALTHY"
    assert r["action"] == "CONTINUE"


def test_alpha_warning():
    r = alpha_health({"signal_strength": 0.6, "mfe": 0.7,
                      "mfe_capture": 0.65})
    assert r["band"] in ("WARNING", "WATCH")
    assert r["action"] in ("INCREASE_VALIDATION", "REVIEW_AND_CONTAIN")


def test_alpha_degraded():
    r = alpha_health({"signal_strength": 0.4, "calibration": 0.4,
                      "mfe": 0.5, "mfe_capture": 0.4,
                      "entry_edge": 0.4, "exit_edge": 0.4,
                      "turnover": 2.0, "cost": 2.0,
                      "regime_dependence": 2.0})
    assert r["band"] == "DEGRADED"
    assert r["action"] == "REVIEW_AND_CONTAIN"
