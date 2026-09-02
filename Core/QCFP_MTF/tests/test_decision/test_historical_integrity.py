# coding: utf-8
"""Historical Decision Integrity Test 测试（89 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.historical_integrity import \
    historical_decision_integrity


def _fact():
    return {"decision_id": "H-2024-001", "target": 0.20,
            "permission": "ALLOW"}


def test_integrity_ok_when_replay_consistent():
    r = historical_decision_integrity(
        _fact(), dict(_fact()),
        new_release_counterfactual={"target": 0.35})
    assert r["old_replay_consistent"] is True
    assert r["verdict"] == "INTEGRITY_OK"
    assert r["historical_fact_immutable"] is True
    assert r["counterfactual_separate"] is True


def test_integrity_failed_on_fact_change():
    replay = dict(_fact())
    replay["target"] = 0.45
    r = historical_decision_integrity(_fact(), replay)
    assert r["verdict"] == "INTEGRITY_FAILED"
    assert r["old_replay_consistent"] is False


def test_counterfactual_never_overwrites_fact():
    r = historical_decision_integrity(
        _fact(), dict(_fact()),
        new_release_counterfactual={"target": 0.60})
    assert r["historical_fact"] == _fact()
    assert r["historical_fact"]["target"] == 0.20
