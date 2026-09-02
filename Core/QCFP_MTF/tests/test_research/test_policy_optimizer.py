# coding: utf-8
"""Decision Policy Optimizer 测试（44 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.research.policy_optimizer import optimize_policy


def _candidates():
    return [
        {"state": "ALLOW+Bull+STRONG", "action": "BUY",
         "expected_value": 0.12, "position": 0.05},
        {"state": "ALLOW+Sideway+STRONG", "action": "HOLD",
         "expected_value": 0.06, "position": 0.05},
        {"state": "BLOCK+Bear", "action": "EXIT",
         "expected_value": 0.01, "position": 0.0},
    ]


def test_policy_optimizer_recommends_best():
    r = optimize_policy(_candidates())
    assert r["recommended"]["state"] == "ALLOW+Bull+STRONG"
    assert r["optimization_guarded"] is False


def test_policy_optimizer_governance_guard():
    cands = _candidates()
    cands[0]["position"] = 0.30    # 超治理上限
    r = optimize_policy(cands, governance_boundaries={"max_position": 0.10,
                                                      "forbidden_actions": ()})
    assert r["optimization_guarded"] is True
    assert len(r["governance_violations"]) >= 1


def test_forbidden_actions_filtered():
    r = optimize_policy(_candidates(),
                        governance_boundaries={
                            "max_position": 0.10,
                            "forbidden_actions": ("EXIT",)})
    assert r["recommended"]["action"] != "EXIT"
