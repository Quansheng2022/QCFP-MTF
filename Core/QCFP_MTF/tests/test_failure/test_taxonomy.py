# coding: utf-8
"""Failure Taxonomy Engine 测试（48 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.failure.failure_modes import (CORRECTIVE_ACTIONS,
                                            FAILURE_MODES, FailureModeDB,
                                            classify_failure)


def test_new_failure_codes():
    assert FAILURE_MODES["F13"] == "WRONG_REGIME"
    assert FAILURE_MODES["F14"] == "OVERSIZING"
    assert FAILURE_MODES["F15"] == "EXECUTION_FAILURE"


def test_classify_failure_new_codes():
    codes = classify_failure({"net_return": -0.05, "wrong_regime": True,
                              "oversized": True, "execution_failure": True})
    assert "F13" in codes and "F14" in codes and "F15" in codes


def test_taxonomy_summary():
    db = FailureModeDB()
    db.record("F02", cost=-0.03)
    db.record("F02", cost=-0.05)
    db.record("F06", cost=-0.02)
    s = db.taxonomy_summary()
    assert s["n_failures"] == 3
    assert s["by_code"]["F02"]["loss_contribution"] == -0.08
    assert s["by_code"]["F02"]["frequency"] == 2
    assert s["by_code"]["F02"]["corrective_action"]
    assert CORRECTIVE_ACTIONS["F14"].startswith("启用")


def test_regime_distribution():
    db = FailureModeDB()
    db.record("F02", regime="Bear", cost=-0.02)
    db.record("F02", regime="Sideway", cost=-0.01)
    s = db.taxonomy_summary()
    assert s["by_code"]["F02"]["regime_distribution"] == {
        "Bear": 1, "Sideway": 1}
