# coding: utf-8
"""Module Retirement Governance 测试（40 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.module_retirement import MODULE_LIFECYCLE, \
    advance_module_lifecycle, module_retirement_decision


def test_retirement_decision():
    r = module_retirement_decision("Regime", incremental_alpha=0.001,
                                   complexity_delta=0.08, data_risk=0.5)
    assert r["action"] == "RETIRE"
    assert "INCREMENTAL_ALPHA_ZERO" in r["reasons"]
    assert "COMPLEXITY_UP" in r["reasons"]


def test_keep_module():
    r = module_retirement_decision("Permission", incremental_alpha=0.05,
                                   complexity_delta=0.0, data_risk=0.0)
    assert r["action"] == "KEEP"


def test_review_when_partial():
    r = module_retirement_decision("Wave", incremental_alpha=0.02,
                                   complexity_delta=0.08, data_risk=0.1)
    assert r["action"] == "REVIEW"


def test_lifecycle_advance():
    assert advance_module_lifecycle("PRODUCTION", "RETIRED") == "RETIRED"
    try:
        advance_module_lifecycle("RETIRED", "PRODUCTION")
        raise AssertionError("should raise")
    except ValueError:
        pass
    assert MODULE_LIFECYCLE[-1] == "RETIRED"
