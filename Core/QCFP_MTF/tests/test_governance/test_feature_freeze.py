# coding: utf-8
"""Feature Freeze 测试（30 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.feature_freeze import ALLOWED_WORK, \
    feature_freeze_gate


def test_allowed_work():
    for work in ("bug_fix", "governance_fix", "pit_fix", "replay_fix",
                 "simplification", "retirement"):
        r = feature_freeze_gate(work)
        assert r["allowed"] is True


def test_new_module_default_drop():
    r = feature_freeze_gate("new_alpha_module")
    assert r["allowed"] is False
    assert r["default_decision"] == "DROP"
    assert "已测量" in r["reason"]


def test_new_module_proven_allowed():
    r = feature_freeze_gate(
        "new_alpha_module", measured_problem="Wave 捕获率 65%→目标 75%",
        incremental_value=0.05, oos_ok=True, ablation_ok=True,
        stress_ok=True, shadow_ok=True)
    assert r["allowed"] is True
    assert r["default_decision"] == "KEEP_CANDIDATE"


def test_allowed_work_constant():
    assert "ablation" in ALLOWED_WORK
    assert "stress" in ALLOWED_WORK
