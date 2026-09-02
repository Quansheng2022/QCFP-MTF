# coding: utf-8
"""Production Autonomy Governor 测试（100 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.autonomy import AUTONOMY_LEVELS, AUTONOMY_MATRIX, \
    autonomy_gate, autonomy_report


def test_read_only_level():
    assert autonomy_gate("compute_wave", "READ_ONLY").allowed is False
    assert autonomy_gate("generate_recommendation",
                         "READ_ONLY").allowed is False


def test_controlled_execution_level():
    g = autonomy_gate("auto_reduce_position", "CONTROLLED_EXECUTION")
    assert g.allowed is True
    assert autonomy_gate("trigger_hard_risk_exit",
                         "CONTROLLED_EXECUTION").allowed is True


def test_forbidden_actions_never_allowed():
    for action in ("modify_permission_rule", "modify_risk_cap",
                   "modify_production_model", "modify_pit_definition",
                   "bypass_oos", "bypass_ablation",
                   "self_approve_new_version", "auto_enter_position"):
        g = autonomy_gate(action, "CONTROLLED_EXECUTION")
        assert g.allowed is False
        assert "禁止" in g.reason


def test_autonomy_report():
    r = autonomy_report("CONTROLLED_EXECUTION")
    assert "auto_reduce_position" in r["allowed"]
    assert "modify_permission_rule" in r["forbidden"]
    assert len(AUTONOMY_LEVELS) == 4
    assert AUTONOMY_MATRIX["self_approve_new_version"] == "FORBIDDEN"
