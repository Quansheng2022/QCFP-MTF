# coding: utf-8
"""Version Impact Release Gate 测试（Release 3：新 23 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.version_impact import change_severity, \
    version_impact_release_gate


def test_severity_levels():
    assert change_severity(["primary_reason"]) == 1
    assert change_severity(["setup_type"]) == 2
    assert change_severity(["target_position"]) == 3
    assert change_severity(["institutional_permission"]) == 4
    assert change_severity([]) == 0


def test_permission_flip_requires_full():
    r = version_impact_release_gate({
        "n_decisions": 100, "flip_rate": 0.18,
        "flips": [{"flipped_fields": ["institutional_permission"]}],
        "field_flip_counts": {"permission": 2}})
    assert r["high_risk_flips"] is True
    assert r["validation_required"] == \
        "FULL_OOS_ABLATION_STRESS_SHADOW_HUMAN"
    assert r["version_impact_report_required"] is True


def test_no_flip_ok():
    r = version_impact_release_gate({
        "n_decisions": 100, "flip_rate": 0.0, "flips": [],
        "field_flip_counts": {}})
    assert r["verdict"] == "OK"
