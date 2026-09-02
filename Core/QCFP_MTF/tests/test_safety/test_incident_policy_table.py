# coding: utf-8
"""Incident Policy Table 测试（新 39 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.safety.incident_protocol import incident_policy_table


def _keys():
    return ("new_decision_allowed", "new_order_allowed",
            "risk_reduction_allowed", "forced_liquidation",
            "replay_required", "human_approval_required")


def test_system_failure_not_force_liquidation():
    table = incident_policy_table()
    sf = table["DECISION_HALTED_SYSTEM_FAILURE"]
    assert sf["forced_liquidation"] is False
    assert sf["new_decision_allowed"] is False
    assert sf["replay_required"] is True
    mr = table["DECISION_HALTED_MARKET_RISK"]
    assert mr["forced_liquidation"] is True
    assert mr["replay_required"] is False


def test_all_incidents_have_full_policy():
    table = incident_policy_table()
    for state, policy in table.items():
        if state == "rule":
            continue
        for k in _keys():
            assert k in policy, f"{state} 缺 {k}"


def test_normal_allows_decisions():
    assert incident_policy_table()["NORMAL"]["new_decision_allowed"] \
        is True
